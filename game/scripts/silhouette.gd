extends RefCounted
## Builds the mouse-passthrough polygon.
##
## On Windows the passthrough region also clips *drawing*, so the polygon has to
## cover every visible pixel: the pet's alpha silhouette plus any visible
## bubble / panel / menu rectangles.  Row extents always produce a simple
## (x-monotone) polygon, which is the only shape the OS region API accepts.

const ROWS := 96
const PAD := 6.0
const ALPHA_CUTOFF := 0.2
const NECK := 28.0

# The loaded silhouette is immutable. Cache source-row bounds once, rather
# than scanning the whole bitmap again whenever a card opens or closes.
static var _cached_image: Image
static var _cached_rows: Array[Vector2i] = []


static func _source_rows(image: Image) -> Array[Vector2i]:
	if image == _cached_image:
		return _cached_rows
	_cached_image = image
	_cached_rows.clear()
	var rgba := image.duplicate() as Image
	rgba.convert(Image.FORMAT_RGBA8)
	var bytes := rgba.get_data()
	var width := rgba.get_width()
	for y in rgba.get_height():
		var first := -1
		var last := -1
		for x in width:
			if bytes[(y * width + x) * 4 + 3] > int(ALPHA_CUTOFF * 255):
				if first < 0:
					first = x
				last = x
		_cached_rows.append(Vector2i(first, last))
	return _cached_rows


static func full_rect(win_size: Vector2) -> PackedVector2Array:
	return PackedVector2Array([
		Vector2(0, 0),
		Vector2(win_size.x, 0),
		Vector2(win_size.x, win_size.y),
		Vector2(0, win_size.y),
	])


static func build(
	image: Image,
	sprite_rect: Rect2,
	extra_rects: Array,
	win_size: Vector2
) -> PackedVector2Array:
	if image == null or sprite_rect.size.x <= 0.0 or sprite_rect.size.y <= 0.0:
		return full_rect(win_size)

	var img_w := image.get_width()
	var img_h := image.get_height()
	if img_w <= 0 or img_h <= 0:
		return full_rect(win_size)
	var source_rows := _source_rows(image)
	var band_height := win_size.y / float(ROWS)

	var lefts: Array[float] = []
	var rights: Array[float] = []
	var ys: Array[float] = []
	lefts.resize(ROWS)
	rights.resize(ROWS)
	ys.resize(ROWS)

	# Scan the whole window height: the bubble / hover panel sit above the sprite
	# and would be clipped away if the polygon only covered the sprite's rows.
	for i in ROWS:
		var win_y := (float(i) + 0.5) / float(ROWS) * win_size.y
		ys[i] = win_y
		lefts[i] = INF
		rights[i] = -INF

		if win_y + band_height < sprite_rect.position.y or win_y - band_height > sprite_rect.end.y:
			continue
		# Both endpoints of an interpolated polygon edge must cover every
		# source row between them. A single centre scan can miss a fingertip.
		var from_y := clampi(int(floor((win_y - band_height - sprite_rect.position.y) / sprite_rect.size.y * img_h)), 0, img_h - 1)
		var to_y := clampi(int(ceil((win_y + band_height - sprite_rect.position.y) / sprite_rect.size.y * img_h)), 0, img_h - 1)
		var first := -1
		var last := -1
		for y in range(from_y, to_y + 1):
			var extent := source_rows[y]
			if extent.x >= 0:
				first = extent.x if first < 0 else mini(first, extent.x)
				last = maxi(last, extent.y)

		if first >= 0:
			lefts[i] = sprite_rect.position.x + float(first) / float(img_w) * sprite_rect.size.x
			rights[i] = sprite_rect.position.x + float(last + 1) / float(img_w) * sprite_rect.size.x

	for rect in extra_rects:
		if typeof(rect) != TYPE_RECT2:
			continue
		var r: Rect2 = rect
		# Keep one full scan row beyond the UI edge. Otherwise interpolation
		# toward the narrow connector cuts diagonally through panel corners.
		var row_height := win_size.y / float(ROWS)
		for i in ROWS:
			if ys[i] >= r.position.y - row_height and ys[i] <= r.end.y + row_height:
				lefts[i] = minf(lefts[i], r.position.x)
				rights[i] = maxf(rights[i], r.end.x)

	# Rows without any coverage inherit from the nearest covered row, so the
	# polygon stays connected instead of collapsing to zero width.
	var has_any := false
	for i in ROWS:
		if lefts[i] <= rights[i]:
			has_any = true
			break
	if not has_any:
		return full_rect(win_size)
	# Do not extend an invisible input-catching strip above/below the content.
	# Only internal gaps between the pet and an open panel need a connector.
	var first_row := 0
	var last_row := ROWS - 1
	while first_row < last_row and lefts[first_row] > rights[first_row]:
		first_row += 1
	while last_row > first_row and lefts[last_row] > rights[last_row]:
		last_row -= 1

	# Rows between two bands (e.g. the gap between bubble and head) get a narrow
	# neck instead of inheriting a full band's width: the polygon must stay
	# connected, but the empty gap should stay click-through.
	for i in range(first_row, last_row + 1):
		if lefts[i] <= rights[i]:
			continue
		var above := -1
		var below := -1
		for j in range(i - 1, -1, -1):
			if lefts[j] <= rights[j]:
				above = j
				break
		for j in range(i + 1, ROWS):
			if lefts[j] <= rights[j]:
				below = j
				break
		var center := win_size.x * 0.5
		if above >= 0 and below >= 0:
			center = ((lefts[above] + rights[above]) + (lefts[below] + rights[below])) * 0.25
		elif above >= 0:
			center = (lefts[above] + rights[above]) * 0.5
		elif below >= 0:
			center = (lefts[below] + rights[below]) * 0.5
		lefts[i] = center - NECK * 0.5
		rights[i] = center + NECK * 0.5

	var points := PackedVector2Array()
	var half_row := win_size.y / float(ROWS) * 0.5
	points.append(Vector2(clampf(rights[first_row] + PAD, 0, win_size.x),
		maxf(0, ys[first_row] - half_row - PAD)))
	for i in range(first_row, last_row + 1):
		var y := clampf(ys[i], 0.0, win_size.y)
		points.append(Vector2(clampf(rights[i] + PAD, 0.0, win_size.x), y))
	points.append(Vector2(clampf(rights[last_row] + PAD, 0, win_size.x),
		minf(win_size.y, ys[last_row] + half_row + PAD)))
	points.append(Vector2(clampf(lefts[last_row] - PAD, 0, win_size.x),
		minf(win_size.y, ys[last_row] + half_row + PAD)))
	for i in range(last_row, first_row - 1, -1):
		var y := clampf(ys[i], 0.0, win_size.y)
		points.append(Vector2(clampf(lefts[i] - PAD, 0.0, win_size.x), y))
	points.append(Vector2(clampf(lefts[first_row] - PAD, 0, win_size.x),
		maxf(0, ys[first_row] - half_row - PAD)))
	return points
