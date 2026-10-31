"""Register painted underlays and keep each visible body part in one layer.

The source plates are deliberately armless. Arms are the original independent
attachments; moving them must never expose a blurred copy of the old sleeve.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops

ROOT = Path(__file__).resolve().parents[1]


def registered(path, scale, offset):
    image = Image.open(ROOT / path).convert("RGBA")
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (1024, 1024))
    canvas.alpha_composite(image, offset)
    # Generated transparent plates may contain invisible alpha speckles.
    canvas.putalpha(canvas.getchannel("A").point(lambda a: 0 if a < 12 else a))
    return canvas


def region(image):
    box = image.getbbox()
    return (image.crop(box), box) if box else (Image.new("RGBA", (1, 1)), (0, 0, 1, 1))


def lower(image, y):
    image = image.copy()
    ImageDraw.Draw(image).rectangle((0, 0, 1023, y - 1), fill=(0, 0, 0, 0))
    return image


def upper(image, y):
    image = image.copy()
    ImageDraw.Draw(image).rectangle((0, y, 1023, 1023), fill=(0, 0, 0, 0))
    return image


def repair_layers(layers):
    import side_art

    from build_spine import build_face
    front = registered("assets/art/rig_repair/front_armless_v1.png", .78, (31, 28))
    side = registered("assets/art/rig_repair/r34_armless_v1.png", side_art.S, (1, 91))
    layers["body"] = region(lower(front, 542))
    layers["head"] = region(upper(front, 548))
    for name, image in build_face(front, front.load(), registered=True).items():
        layers[name] = region(image)
    blink = registered("assets/art/rig_repair/front_blink_v1.png", .78, (31, 28))
    from build_spine import FACE_RECT
    face = Image.new("RGBA", (1024, 1024))
    face.alpha_composite(blink.crop(FACE_RECT), FACE_RECT[:2])
    layers["eyes_closed"] = region(face)
    layers["eyes_happy"] = region(face)
    for direction in ("left", "right", "down"):
        painted = registered("assets/art/rig_repair/front_" + direction + "_v1.png", .78, (31, 28))
        face = Image.new("RGBA", (1024, 1024))
        face.alpha_composite(painted.crop(FACE_RECT), FACE_RECT[:2])
        layers["eyes_" + direction] = region(face)
    # Half-lidded concentration shares the painted downward expression.
    layers["eyes_half"] = layers["eyes_down"]
    layers["eyes_up"] = layers["eyes_open"]
    # Preserve the painted fingers as a continuous polygon. Skin-colour
    # thresholding confused white highlights with cuffs and punched holes.
    original = Image.open(ROOT / "assets/art/pet_portrait.png").convert("RGBA")
    # The original navy flood included a triangular patch of skirt below the
    # right cuff. That patch flipped over the whale when the forearm bent.
    # Trace the actual cloth/frill edge and put its wrist at the skin seam.
    sleeve_outline = [(544, 546), (558, 553), (570, 566), (576, 578),
        (586, 583), (589, 590), (586, 599), (596, 614), (605, 626),
        (610, 637), (617, 650), (628, 655), (629, 660), (624, 664),
        (621, 667), (619, 671), (614, 674), (610, 673), (606, 678),
        (601, 678), (598, 682), (592, 683), (586, 686), (580, 686),
        (576, 682), (574, 675), (564, 661), (554, 651), (545, 635),
        (537, 621), (532, 609), (530, 593), (532, 574), (538, 557)]
    sleeve_mask = Image.new("L", (4096, 4096))
    ImageDraw.Draw(sleeve_mask).polygon([(x * 4, y * 4) for x, y in sleeve_outline], fill=255)
    sleeve = original.copy()
    sleeve.putalpha(ImageChops.multiply(sleeve.getchannel("A"), sleeve_mask.resize(original.size, Image.Resampling.LANCZOS)))
    layers["arm_fore_r"] = region(lower(sleeve, 606))
    layers["slack_sleeve_r"] = region(sleeve)
    for name, outline in {
        "hand_l": [(325, 670), (345, 683), (340, 691), (325, 705),
                   (318, 705), (317, 701), (312, 704), (307, 701),
                   (305, 695), (308, 686), (315, 678)],
        "hand_rest": [(594, 682), (618, 669), (626, 678), (633, 689),
                      (634, 697), (630, 703), (620, 705), (609, 703),
                      (604, 704), (598, 698), (592, 690)],
    }.items():
        mask = Image.new("L", (4096, 4096))
        ImageDraw.Draw(mask).polygon([(x * 4, y * 4) for x, y in outline], fill=255)
        mask = mask.resize(original.size, Image.Resampling.LANCZOS)
        hand = original.copy()
        hand.putalpha(ImageChops.multiply(hand.getchannel("A"), mask))
        layers[name] = region(hand)
    for name in ("hair_back", "hair_l", "hair_r", "skirt", "tail", "s_hair_back"):
        layers[name] = region(Image.new("RGBA", (1, 1)))
    up = registered("assets/art/rig_repair/up_armless_v1.png", side_art.S, (-4, 100))
    layers["s_body"] = region(lower(side, 528))
    layers["s_body_up"] = region(lower(up, 528))
    layers["s_head_rest"] = region(upper(side, 532))
    layers["s_head"] = region(upper(up, 532))
    from hand_cut import cut_all, place_hand
    hands = cut_all()
    # Cut along the painted sleeve contour, not by navy/white colour. The
    # latter picked up apron frills and left jagged holes in the sleeve.
    side_original = side_art.register("r34")
    contours = {
        "l": [(390, 562), (423, 559), (444, 564), (449, 580),
              (448, 597), (441, 609), (433, 613), (429, 622),
              (421, 634), (412, 645), (410, 655), (407, 662),
              (409, 672), (409, 682), (405, 685), (401, 684),
              (393, 696), (387, 703), (378, 705), (373, 702),
              (366, 705), (355, 702), (346, 695), (344, 686),
              (344, 675), (350, 667), (347, 660), (350, 653),
              (360, 641), (367, 640), (370, 632), (374, 615),
              (386, 608), (379, 599), (376, 583), (380, 571)],
        "r": [(566, 562), (579, 562), (588, 573), (590, 588),
              (585, 602), (589, 610), (600, 623), (605, 633),
              (606, 639), (611, 641), (620, 652), (621, 658),
              (626, 660), (631, 665), (628, 675), (631, 679),
              (636, 687), (639, 695), (636, 701), (630, 705),
              (623, 703), (613, 695), (608, 689), (602, 682),
              (598, 679), (594, 672), (591, 665), (586, 658),
              (584, 645), (580, 630), (573, 621), (566, 612), (562, 600)],
    }
    for tag, outline in contours.items():
        mask = Image.new("L", (4096, 4096))
        ImageDraw.Draw(mask).polygon([(x * 4, y * 4) for x, y in outline], fill=255)
        arm = side_original.copy()
        arm.putalpha(ImageChops.multiply(arm.getchannel("A"), mask.resize(arm.size, Image.Resampling.LANCZOS)))
        layers["s_arm_up_" + tag] = region(upper(arm, 618))
        layers["s_arm_fore_" + tag] = region(lower(arm, 606))
    for side, wrist, angle in (("l", (377, 669), 120), ("r", (604, 661), 59)):
        sprite, box = layers["s_arm_fore_" + side]
        fore = Image.new("RGBA", (1024, 1024))
        fore.alpha_composite(sprite, box[:2])
        pixels = fore.load()
        import math
        dx, dy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        for y in range(box[1], box[3]):
            for x in range(box[0], box[2]):
                if (x - wrist[0]) * dx + (y - wrist[1]) * dy > 2:
                    pixels[x, y] = (0, 0, 0, 0)
        fore.alpha_composite(place_hand(*hands["open_r"], wx=wrist[0], wy=wrist[1],
                                       ang=angle, scale=.8, mirror=(side == "l")))
        layers["s_arm_fore_" + side + "_open"] = region(fore)
    layers["book_hand"] = region(place_hand(*hands["open_r"], wx=424, wy=610,
                                            ang=-25, scale=.7, mirror=True))
    # Painted two-handed grip. Keeping the wrists, fingers and ceramic cup
    # on one control prevents a floating cup or hands drifting off its rim.
    # v2 repairs the painted double cuffs / bare skin between sleeve sections.
    source = Image.open(ROOT / "assets/art/rig_repair/drink_two_hands_v2.png").convert("RGBA")
    outline = [(637, 617), (704, 607), (765, 592), (789, 556),
               (835, 525), (834, 492), (830, 460), (836, 424),
               (848, 406), (867, 391), (903, 376), (939, 374),
               (964, 387), (989, 391), (1015, 426), (1024, 468),
               (1016, 516), (1038, 551), (1049, 588), (1034, 641),
               (1009, 665), (956, 692), (910, 696), (871, 678),
               (849, 703), (806, 719), (756, 718), (719, 743),
               (677, 744), (649, 726), (627, 695), (620, 658)]
    mask = Image.new("L", source.size)
    ImageDraw.Draw(mask).polygon([(round(x * source.width / 1280), round(y * source.height / 1280)) for x, y in outline], fill=255)
    source.putalpha(ImageChops.multiply(source.getchannel("A"), mask))
    source = source.resize((round(source.width * side_art.S), round(source.height * side_art.S)), Image.Resampling.LANCZOS)
    arms = Image.new("RGBA", (1024, 1024))
    arms.alpha_composite(source, (-4, 100))
    # Each sleeve is continuous from its shoulder to the wrist. Only the
    # elbow and seam rows blend neighbouring joint transforms; the upper arm
    # and forearm themselves rotate on fixed-length bones. Separate rigid
    # cutouts left wedge-shaped gaps when their painted cut edges rotated.
    outlines = {
        "drink_arms": [(580, 419), (590, 398), (608, 382), (631, 369),
            (650, 365), (674, 366), (687, 377), (697, 379), (704, 388),
            (708, 396), (714, 404), (714, 416), (719, 425), (714, 439),
            (709, 450), (709, 459), (717, 478), (722, 490), (714, 499),
            (684, 501), (677, 491), (675, 471), (667, 464), (650, 469),
            (637, 469), (631, 461), (628, 472), (623, 502), (609, 505),
            (592, 497), (582, 487), (588, 469), (581, 457), (578, 442)],
        "d_upper_l": [(450, 539), (481, 533), (506, 535), (531, 535),
            (548, 550), (561, 573), (557, 592), (539, 603), (518, 609),
            (500, 621), (478, 622), (460, 610), (448, 587), (446, 559)],
        "d_fore_l": [(450, 539), (481, 533), (506, 535), (525, 532), (531, 514), (550, 501),
            (560, 488), (582, 481), (603, 489), (620, 495), (625, 507),
            (632, 516), (631, 532), (622, 548), (620, 559), (605, 575),
            (588, 585), (570, 594), (548, 601), (518, 609), (500, 621),
            (478, 622), (460, 610), (448, 587), (446, 559)],
        "d_upper_r": [(617, 524), (641, 515), (661, 519), (678, 531),
            (695, 547), (695, 563), (680, 575), (663, 583), (639, 584),
            (620, 577), (613, 555)],
        "d_fore_r": [(617, 524), (641, 515), (657, 515), (659, 497), (669, 481), (684, 476), (702, 481),
            (718, 490), (727, 506), (730, 522), (724, 540), (715, 549),
            (702, 559), (680, 575), (663, 583), (639, 584), (620, 577), (613, 555)],
    }
    for name, points in outlines.items():
        mask = Image.new("L", (4096, 4096))
        ImageDraw.Draw(mask).polygon([(x * 4, y * 4) for x, y in points], fill=255)
        piece = arms.copy()
        piece.putalpha(ImageChops.multiply(piece.getchannel("A"), mask.resize(arms.size, Image.Resampling.LANCZOS)))
        layers[name] = region(piece)
    source = Image.open(ROOT / "assets/art/rig_repair/work_notebook_v1.png").convert("RGBA")
    from deepseek_whale import render_whale
    logo = render_whale(round(65 * source.width / 1280), (246, 249, 255, 255))
    source.alpha_composite(logo, (round(552 * source.width / 1280), round(712 * source.height / 1280)))
    outline = [(505, 584), (531, 586), (575, 633), (579, 674),
               (642, 685), (683, 651), (739, 623), (788, 637),
               (783, 684), (795, 706), (796, 739), (808, 775),
               (797, 804), (757, 826), (705, 817), (680, 803),
               (637, 799), (599, 784), (530, 775), (497, 792),
               (461, 795), (435, 782), (414, 758), (410, 732),
               (420, 707), (440, 685), (466, 681), (477, 661),
               (492, 645), (492, 617), (498, 597)]
    mask = Image.new("L", source.size)
    ImageDraw.Draw(mask).polygon([(round(x * source.width / 1280), round(y * source.height / 1280)) for x, y in outline], fill=255)
    source.putalpha(ImageChops.multiply(source.getchannel("A"), mask))
    source = source.resize((round(source.width * side_art.S), round(source.height * side_art.S)), Image.Resampling.LANCZOS)
    arms = Image.new("RGBA", (1024, 1024))
    arms.alpha_composite(source, (30, 100))
    layers["work_arms"] = region(arms)


def drink_sleeve_weights(side):
    import math
    from build_spine import smoothstep, BONES
    source_joints = {name: (x, y) for name, _parent, x, y in BONES}
    tag = side.upper()
    upper_bone, fore_bone = "d_arm" + tag + "1", "d_arm" + tag + "2"
    sx, sy = source_joints[upper_bone]
    ex, ey = source_joints[fore_bone]
    wx, wy = source_joints["d_hand" + tag]
    length = math.hypot(wx - ex, wy - ey)
    dx, dy = (wx - ex) / length, (wy - ey) / length

    def weights(x, y):
        along = (x - ex) * dx + (y - ey) * dy
        # Bend only the short strip around the elbow, preserving the full
        # painted contour through the joint (no independent cut edges).
        fore = smoothstep(-12, 16, along)
        grip = smoothstep(length - 18, length + 1, along)
        root = 1 - smoothstep(10, 34, math.hypot(x - sx, y - sy))
        return {"chest": root, upper_bone: (1 - root) * (1 - fore),
                fore_bone: (1 - root) * fore * (1 - grip),
                "drink_prop": (1 - root) * fore * grip}
    return weights


def slack_sleeve_weights(x, y):
    import math
    from build_spine import smoothstep, BONES
    source_joints = {name: (sx, sy) for name, _parent, sx, sy in BONES}
    sx, sy = source_joints["armR1"]
    ex, ey = source_joints["armR2"]
    wx, wy = source_joints["handR"]
    length = math.hypot(wx - ex, wy - ey)
    along = ((x - ex) * (wx - ex) + (y - ey) * (wy - ey)) / length
    fore = smoothstep(-10, 14, along)
    root = 1 - smoothstep(8, 40, math.hypot(x - sx, y - sy))
    return {"chest": root, "armR1": (1 - root) * (1 - fore),
            "armR2": (1 - root) * fore}


def side_shoulder_weights(side):
    from build_spine import smoothstep
    import math
    def weights(x, y):
        anchor = (436, 566) if side == "l" else (568, 566)
        arm = smoothstep(5, 35, math.hypot(x - anchor[0], y - anchor[1]))
        return {"s_armL1" if side == "l" else "s_armR1": arm, "chest": 1 - arm}
    return weights


def work_weights(x, y):
    # Small strokes stay local to the writing hand/pen; the support hand and
    # book cannot chase them. Sleeve roots retain a little chest influence.
    x_weight = max(0.0, 1.0 - abs(x - 404) / 55)
    y_weight = max(0.0, min(1.0, (610 - y) / 20))
    nib = x_weight * y_weight
    shoulder = .35 if (x < 350 or x > 565) else 0.0
    return {"write_tip": nib * (1 - shoulder), "work_prop": (1 - nib) * (1 - shoulder), "chest": shoulder}

