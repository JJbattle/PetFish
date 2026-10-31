"""Final pose choreography, applied before converting screen coordinates.

Attachment changes are discrete: cross-fading two anatomical views produces
four eyes/hands. A prop's hands replace resting hands on the same frame.
"""
from copy import deepcopy


def refine(skeleton):
    from build_spine import att, col, tr, ro, sc, ikf, ik_reset, hop_keys, hop_scale
    animations = skeleton["animations"]
    # The angular underlay owns all the hair below its head. Never draw the
    # original full-height hair plate behind a second painted head.
    for animation in animations.values():
        slots = animation.setdefault("slots", {})
        slots["s_hair_back"] = {"attachment": [{"time": 0}]}
        slots["drink_arms"] = {"attachment": att([(0, None)])}
        slots["work_arms"] = {"attachment": att([(0, None)])}
        slots["book_hand"] = {"attachment": att([(0, None)])}

    setup = {s["name"]: s.get("attachment") for s in skeleton["slots"]}
    side_parts = ("s_body", "s_head", "s_arm_up_l", "s_arm_up_r", "s_arm_fore_l", "s_arm_fore_r")

    def side_clip(T, turn_in=None, turn_out=None, raised=False):
        slots = {s: {"attachment": att([(0, n)]), "rgba": col([(0, 1)])} for s, n in setup.items()}
        for slot, default in setup.items():
            if default:
                keys = [(0, default), (turn_in, None)] if turn_in is not None else [(0, None)]
                if turn_out is not None:
                    keys.append((turn_out, default))
                slots[slot]["attachment"] = att(keys)
        for slot in side_parts:
            name = "s_head" if raised and slot == "s_head" else "s_head_rest" if slot == "s_head" else slot
            keys = [(0, None), (turn_in, name)] if turn_in is not None else [(0, name)]
            if turn_out is not None:
                keys.append((turn_out, None))
            slots[slot]["attachment"] = att(keys)
        return {"slots": slots, "ik": ik_reset(),
                "bones": {"root": {"translate": tr([(0, 0, 0), (T, 0, 0)])}}}

    # A real three-quarter view, with the offering hand pointing screen-right.
    # The alternate pose keeps the other hand at the chest instead of offering
    # two palms. Keep the painted side face still rather than warping its eyes.
    for name, chest_hand in (("present", False), ("present2", True)):
        pose = {"s_armR1": -25, "s_armR2": -50}
        if chest_hand:
            pose.update({"s_armL1": -20, "s_armL2": -120})
        for phase, T in (("", 3.6), ("_in", .8), ("_out", .7)):
            a = side_clip(T, turn_in=.16 if phase == "_in" else None,
                          turn_out=.60 if phase == "_out" else None)
            for bone, angle in pose.items():
                pairs = [(0, angle), (T / 2, angle + 1.5), (T, angle)]
                if phase == "_in":
                    pairs = [(0, 0), (.18, 0), (.66, angle), (T, angle)]
                elif phase == "_out":
                    pairs = [(0, angle), (.10, angle), (.54, 0), (T, 0)]
                a["bones"][bone] = {"rotate": ro(pairs)}
            for side in ("lr" if chest_hand else "r"):
                slot = "s_arm_fore_" + side
                keys = [(0, slot + "_open")]
                if phase == "_in":
                    keys = [(0, None), (.16, slot), (.34, slot + "_open")]
                elif phase == "_out":
                    keys += [(.45, slot), (.60, None)]
                a["slots"][slot]["attachment"] = att(keys)
            animations[name + phase] = a

    # Rotate the cup/grip around the elbow region; non-stretching two-bone IK
    # turns each continuous sleeve's upper-arm and forearm sections.
    for name in ("drink_in", "drink_sip", "drink_sip2", "drink_sip3", "drink_out"):
        entering, leaving = name == "drink_in", name == "drink_out"
        T = 1.4 if entering else 1.3 if leaving else 1.5
        a = side_clip(T, turn_in=.16 if entering else None,
                      turn_out=1.18 if leaving else None, raised=not entering)
        slots = a["slots"]
        for part in ("s_arm_up_l", "s_arm_up_r", "s_arm_fore_l", "s_arm_fore_r"):
            slots[part]["attachment"] = att([(0, None), (.16, part), (.42, None)] if entering
                                             else [(0, None), (1.02, part), (1.18, None)] if leaving
                                             else [(0, None)])
        slots["drink_arms"]["attachment"] = att([(0, None), (.42, "drink_arms")] if entering
                                                  else [(0, "drink_arms"), (1.02, None)] if leaving
                                                  else [(0, "drink_arms")])
        for part in ("d_fore_l", "d_fore_r"):
            slots[part]["attachment"] = att([(0, None), (.42, part)] if entering
                else [(0, part), (1.02, None)] if leaving else [(0, part)])
        if entering:
            slots["s_head"]["attachment"] = att([(0, None), (.16, "s_head_rest"), (.88, "s_head")])
            slots["s_body"]["attachment"] = att([(0, None), (.16, "s_body"), (.88, "s_body_up")])
            motion = [(0, 14), (.42, 14), (.70, 9), (1.12, 0), (T, 0)]
        elif leaving:
            slots["s_head"]["attachment"] = att([(0, "s_head"), (.42, "s_head_rest"), (1.18, None)])
            slots["s_body"]["attachment"] = att([(0, "s_body_up"), (.42, "s_body"), (1.18, None)])
            motion = [(0, 0), (.16, 0), (.60, 9), (.98, 14), (T, 14)]
        else:
            slots["s_body"]["attachment"] = att([(0, "s_body_up")])
            # Each clip is one sip: gently tip up, hold, release and swallow.
            # Identical endpoints join into 1/2/3 sips without a pop.
            motion = [(0, 0), (.22, -1.8), (.46, -1.8), (.60, .6),
                      (.78, -.4), (.95, 0), (T, 0)]
            # Whole-character breathing preserves lip/rim contact.
            a["bones"]["root"]["translate"] = tr([(0, 0, 0), (.75, 0, -.8), (T, 0, 0)])
        a["bones"]["drink_lift"] = {"rotate": ro(motion)}
        a["ik"]["d_ik_l"] = ikf([(0, 1), (T, 1)], True)
        a["ik"]["d_ik_r"] = ikf([(0, 1), (T, 1)], True)
        animations[name] = a

    # Use the painted notebook and anatomically connected bent sleeves. The
    # native vector whale is stamped onto its blank cover by rig_repair.py.
    for name in ("working", "working_in", "working_out"):
        entering, leaving = name.endswith("_in"), name.endswith("_out")
        T = 1.0 if entering else .95 if leaving else 4.6
        a = animations[name]
        a["ik"] = ik_reset()
        a["bones"] = {"root": {"translate": tr([(0, 0, 0), (T / 2, 0, -.8), (T, 0, 0)])}}
        on, off = .30, .70
        for slot in ("book", "book_hand", "pen", "pen_hand", "arm_fore_l_front", "arm_fore_r_front", "hand_l_front", "hand_r_front"):
            a["slots"][slot] = {"attachment": att([(0, None)])}
        for slot in ("arm_up_l", "arm_up_r", "arm_fore_l", "arm_fore_r", "hand_l", "hand_r"):
            default = setup[slot]
            a["slots"][slot] = {"attachment": att([(0, default), (on, None)] if entering else [(0, None), (off, default)] if leaving else [(0, None)]), "rgba": col([(0, 1)])}
        a["slots"]["work_arms"] = {"attachment": att([(0, None), (on, "work_arms")] if entering else [(0, "work_arms"), (off, None)] if leaving else [(0, "work_arms")])}
        a["bones"]["work_prop"] = {"translate": tr([(0, 0, 44), (on, 0, 44), (.8, 0, 0), (T, 0, 0)] if entering else [(0, 0, 0), (.2, 0, 0), (off, 0, 44), (T, 0, 44)] if leaving else [(0, 0, 0), (T, 0, 0)])}
        if not entering and not leaving:
            a["bones"]["write_tip"] = {"translate": tr([(0, 0, 0), (.25, 3, 1), (.5, -2, 0), (.75, 2, 1), (1, -2, 0), (1.25, 3, 1), (1.5, 0, 0), (2.25, 0, 0), (2.5, 2, 1), (2.75, -2, 0), (3, 2, 1), (3.25, -2, 0), (3.5, 3, 1), (3.75, 0, 0), (T, 0, 0)])}

    # Seamless repeated hops with both hands waving. The runtime holds this
    # loop until acknowledgement (or until the pending session resumes).
    from build_spine import base_anim, arms_front
    for name in ("needs_input", "needs_input_hop", "hop_sit", "hop_alarm", "hop_memo", "water_remind"):
        T = 1.2
        a = base_anim(T, eyes=att([(0, "eyes_open"), (.28, "eyes_happy"), (.50, "eyes_open")]),
                      mouth=att([(0, "mouth_smile")]))
        arms_front(a)
        a["slots"] = {slot: a.pop(slot) for slot in list(a) if slot in setup}
        a["bones"] = {
            "root": {"translate": tr([(0, 0), (.12, 4), (.30, -30), (.42, -36), (.55, -24), (.72, 0), (.80, 3), (.94, 0), (T, 0)])},
            "head": {"rotate": ro([(0, 0), (.32, -2), (.72, 2), (T, 0)])},
        }
        for side, sign in (("L", 1), ("R", -1)):
            a["bones"]["arm" + side + "1"] = {"rotate": ro([(0, sign * 46), (.30, sign * 64), (.52, sign * 54), (.72, sign * 64), (T, sign * 46)])}
            a["bones"]["arm" + side + "2"] = {"rotate": ro([(0, sign * 45), (.30, sign * 64), (.46, sign * 38), (.62, sign * 67), (.82, sign * 40), (T, sign * 45)])}
            tag = side.lower()
            a["slots"]["arm_up_" + tag] = {"attachment": att([(0, None)])}
            a["slots"]["arm_up_" + tag + "_front"] = {"attachment": att([(0, "arm_up_" + tag)])}
            a["slots"]["hand_" + tag + "_front"] = {"attachment": att([(0, "hand_open_l" if tag == "l" else "hand_open")])}
        animations[name] = a

    # Hand ownership changes atomically, including the sub-millisecond keys
    # which previously left two semi-transparent pairs during slack entry.
    for name, swap in (("slack_in", .66), ("slack_out", .30)):
        a = animations[name]
        entering = name.endswith("_in")
        for side, default in (("l", "hand_l"), ("r", "hand_rest")):
            a["slots"]["hand_" + side] = {
                "attachment": att([(0, default), (swap, None)] if entering else [(0, None), (swap, default)]),
                "rgba": col([(0, 1)])}
            prop = "fish_hand_" + side
            a["slots"][prop] = {
                "attachment": att([(0, None), (swap, prop)] if entering else [(0, prop), (swap, None)]),
                "rgba": col([(0, 1)])}

    for name in ("slack", "slack_in", "slack_out"):
        a = animations[name]
        # Lift the whale into the short arm's reachable cradle, and draw the
        # supporting palm at its lower contour instead of over its belly.
        for key in a["bones"]["fish"]["translate"]:
            key["y"] -= 32
        a["slots"]["fish_hand_l_front"] = {"attachment": att([(0, None)])}
        # Both segments of the stroking arm stay in front of the whale in
        # entry/hold/exit. Hiding its upper arm behind the prop made the cuff
        # look severed; switching the forearm's layer only in the loop also
        # made the arm pop into existence after the hand had arrived.
        for part in ("arm_up_r", "arm_fore_r"):
            a["slots"][part] = {"attachment": att([(0, None)])}
        a["slots"]["arm_up_r_front"] = {"attachment": att([(0, "slack_sleeve_r")])}
        a["slots"]["arm_fore_r_front"] = {"attachment": att([(0, None)])}
        if name != "slack":
            a["slots"]["hand_r_front"] = a["slots"]["hand_r"]
            a["slots"]["hand_r"] = {"attachment": att([(0, None)])}
            a["slots"]["fish_hand_r_front"] = a["slots"]["fish_hand_r"]
            a["slots"]["fish_hand_r"] = {"attachment": att([(0, None)])}
        if name == "slack":
            a["slots"]["fish_hand_l"] = {"attachment": att([(0, "fish_hand_l")])}
            # The old target crossed the arm chain's minimum reach radius,
            # making IK fold the sleeve back over the palm during each stroke.
            a["bones"]["slackR"] = {
                "translate": tr([(0, 0, 0), (.9, -9, 1), (2.1, 9, -1),
                                 (3.3, -9, 1), (4.5, 9, -1), (5.6, -4, 0), (6, 0, 0)]),
                "rotate": ro([(0, 5), (.9, 8), (2.1, 2), (3.3, 8),
                              (4.5, 2), (5.6, 6), (6, 5)])}

    # Each clip owns the complete slot state. A preceding hug/presentation
    # must not leave front-layer fingers or an invisible torso behind.
    for a in animations.values():
        a.setdefault("bones", {}).setdefault("drink_lift", {"rotate": ro([(0, 0)])})
        for slot, default in setup.items():
            channel = a["slots"].setdefault(slot, {})
            channel.setdefault("attachment", att([(0, default)]))
            channel.setdefault("rgba", col([(0, 1)]))

