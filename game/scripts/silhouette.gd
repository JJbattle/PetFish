extends RefCounted
## Builds the mouse-passthrough polygon.
##
## On Windows the passthrough region also clips *drawing*, so the polygon has to
## cover every visible pixel: the pet's alpha silhouette plus any visible
## bubble / panel / menu rectangles.  Row extents always produce a simple
## (x-monotone) polygon, which is the only shape the OS region API accepts.

const ROWS := 56
const PAD := 4.0
const ALPHA_CUTOFF := 0.2
const NECK := 28.0


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

		if win_y < sprite_rect.position.y or win_y > sprite_rect.end.y:
			continue
		var t := (win_y - sprite_rect.position.y) / maxf(1.0, sprite_rect.size.y)
		var img_y := clampi(int(t * float(img_h)), 0, img_h - 1)

		var first := -1
		var last := -1
		for x in img_w:
			if image.get_pixel(x, img_y).a > ALPHA_CUTOFF:
				if first < 0:
					first = x
				last = x

		if first >= 0:
			lefts[i] = sprite_rect.position.x + float(first) / float(img_w) * sprite_rect.size.x
			rights[i] = sprite_rect.position.x + float(last + 1) / float(img_w) * sprite_rect.size.x

	for rect in extra_rects:
		if typeof(rect) != TYPE_RECT2:
			continue
		var r: Rect2 = rect
		for i in ROWS:
			if ys[i] >= r.position.y and ys[i] <= r.end.y:
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

	# Rows between two bands (e.g. the gap between bubble and head) get a narrow
	# neck instead of inheriting a full band's width: the polygon must stay
	# connected, but the empty gap should stay click-through.
	for i in ROWS:
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
	for i in ROWS:
		var y := clampf(ys[i], 0.0, win_size.y)
		points.append(Vector2(clampf(rights[i] + PAD, 0.0, win_size.x), y))
	for i in range(ROWS - 1, -1, -1):
		var y := clampf(ys[i], 0.0, win_size.y)
		points.append(Vector2(clampf(lefts[i] - PAD, 0.0, win_size.x), y))
	return points
