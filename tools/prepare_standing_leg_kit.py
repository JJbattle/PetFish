"""Register missing hidden leg art against the existing standing artwork.

Does not build or overwrite production Spine assets. Original visible sock and
shoe pixels are copied without resampling. Bone guides are not anatomy claims.
"""
from pathlib import Path
import json
import hashlib

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/art/standing_leg_kit_v1"
FONT = "C:/Windows/Fonts/msyh.ttc"
SIZE = (1024, 1024)


def canvas():
    return Image.new("RGBA", SIZE)


def save_part(name, im, metadata):
    box = im.getchannel("A").getbbox()
    box = (max(0, box[0]-4), max(0, box[1]-4),
           min(1024, box[2]+4), min(1024, box[3]+4))
    path = OUT / "parts" / (name + ".png")
    path.parent.mkdir(parents=True, exist_ok=True)
    im.crop(box).save(path)
    metadata[name] = {"file": "parts/"+name+".png", "source_rect": list(box),
                      "position_top_left": list(box[:2]), "scale": 1.0}
    return im


def row_segment(alpha, seed):
    lo = hi = seed
    assert alpha[seed] > 128
    while lo > 0 and alpha[lo-1] > 128:
        lo -= 1
    while hi+1 < len(alpha) and alpha[hi+1] > 128:
        hi += 1
    return lo, hi+1


def painted_thigh(plate, side, native):
    """Register each painted row; remove hidden rounded bottom cap, not paint."""
    half = plate.crop((0 if side == "l" else plate.width//2, 0,
                       plate.width//2 if side == "l" else plate.width, plate.height))
    alpha = half.getchannel("A")
    core = alpha.point(lambda a: 255 if a >= 200 else 0)
    # Keep true edge AA but reject any detached generation haze.
    half.putalpha(ImageChops.multiply(alpha, core.filter(ImageFilter.MaxFilter(3))))
    half = half.crop(core.getbbox())
    arr = np.asarray(half)
    result = canvas()
    seed = 435 if side == "l" else 525
    end_l, end_r = row_segment(np.asarray(native)[826, :, 3], seed)
    end_center = (end_l+end_r)/2
    start_center = 442 if side == "l" else 500
    end_width = end_r-end_l
    for y in range(712, 843):
        t = min(1.0, (y-712)/114)
        sy = round((.06+.83*t)*(half.height-1))
        xs = np.where(arr[sy, :, 3] > 150)[0]
        row = half.crop((int(xs[0]), sy, int(xs[-1])+1, sy+1))
        # Constant-width knee support; no inward notch at the joint guide.
        width = round((1-t)*(end_width+4)+t*end_width)
        cx = (1-t)*start_center+t*end_center
        row = row.resize((width, 1), Image.Resampling.LANCZOS)
        # Match the existing skin along the final hidden-to-visible join.
        # This grades generated paint to a native skin scanline, rather than
        # leaving a horizontal colour/outline step at the source boundary.
        amount = max(0.0, min(1.0, (y-798)/27))
        edge = native.crop((end_l,826,end_r,827)).resize((width,1),Image.Resampling.LANCZOS)
        row = Image.blend(row,edge,amount)
        result.paste(row,(round(cx-width/2), y))
    return result


def section(im, lo, hi):
    result = canvas()
    result.paste(im.crop((0, lo, 1024, hi)), (0, lo))
    return result


def native_leg_mask(native, side):
    """Keep front frill with the body, skin/side outlines with the leg.

    Trace the pink skin immediately below the dark hem outline. This is
    intentionally restricted to the two known leg windows, not a whole-width
    y=800 cut (which would also move skirt and hair with the leg).
    """
    a=np.asarray(native)
    low,high=(400,476) if side=="l" else (490,567)
    trace={}
    for x in range(low,high):
        for y in range(808,827):
            strip=a[y:y+3,x,:3].astype(int)
            if np.all((strip[:,0]>180)&(strip[:,0]-strip[:,1]>28)&
                      (strip[:,0]-strip[:,2]>28)):
                trace[x]=y
                break
    assert len(trace)>35, (side,len(trace))
    mask=Image.new("L",SIZE)
    d=ImageDraw.Draw(mask)
    lo,hi=(390,485) if side=="l" else (485,580)
    d.rectangle((lo,826,hi-1,951),fill=255)
    for x in range(low,high):
        nearest=min(trace,key=lambda v:abs(v-x))
        d.line((x,trace.get(x,trace[nearest]),x,826),fill=255)
    return mask


def checker(size):
    im = Image.new("RGBA", size, "#f1f3f7")
    d = ImageDraw.Draw(im)
    for y in range(0, size[1], 12):
        for x in range(0, size[0], 12):
            if (x//12+y//12) % 2:
                d.rectangle((x,y,x+11,y+11), fill="#e2e7ef")
    return im


def main():
    from rig_repair import registered
    OUT.mkdir(parents=True, exist_ok=True)
    native = registered("assets/art/rig_repair/front_armless_v1.png", .78, (31,28))
    native.save(OUT/"sources/standing_registered.png")
    plate = Image.open(OUT/"sources/thigh_plate.png").convert("RGBA")
    metadata = {}
    masters, leg_images, foot_images, uppers = {}, {}, {}, {}
    checks = {}
    removal=Image.new("L",SIZE)
    for side, lo, hi in (("l", 390,485), ("r",485,580)):
        thigh = painted_thigh(plate, side, native)
        # Existing visible skin, frilled cuff, sock, and shoe, exactly as used
        # by repair_layers(). Start below the lowest front hem, not at y=800.
        mask=native_leg_mask(native,side)
        removal=ImageChops.lighter(removal,mask)
        original=native.copy()
        original.putalpha(ImageChops.multiply(native.getchannel("A"),mask))
        master = section(thigh,712,826)
        # Preserve the exact original skin/edge silhouette wherever it can be
        # visible beneath the hem; generated paint only fills hidden roots.
        clip=master.getchannel("A")
        clip_arr=np.asarray(clip).copy()
        clip_arr[810:]=np.minimum(clip_arr[810:],np.asarray(native.getchannel("A"))[810:])
        master.putalpha(Image.fromarray(clip_arr))
        master.paste(native,(0,0),mask)
        master.paste(original.crop((0,826,1024,1024)),(0,826))
        masters[side] = save_part("leg_"+side+"_master",master,metadata)
        leg_images[side] = save_part("leg_"+side+"_full",section(master,712,905),metadata)
        # Primary ankle split is complementary; shared-coordinate weights are
        # still required across this split. Do not duplicate alpha in runtime.
        foot_images[side] = save_part("shoe_"+side,section(master,905,952),metadata)
        uppers[side] = save_part("thigh_"+side,section(master,712,820),metadata)
        save_part("calf_"+side,section(master,780,917),metadata)
        save_part("shoe_"+side+"_overlap_reference",section(master,889,952),metadata)
        save_part("thigh_"+side+"_painted_underlap",thigh,metadata)
        a,b=np.asarray(master),np.asarray(native)
        selected=np.asarray(mask)>0
        checks[side+"_visible_native_pixel_diff"] = int((np.any(a!=b,axis=2)&selected).sum())
        checks[side+"_knee_alpha_width_y800"] = int((a[800,:,3]>128).sum())
        mask_rgba=Image.new("RGBA",SIZE,"white");mask_rgba.putalpha(mask)
        save_part("source_leg_"+side+"_removal_mask",mask_rgba,metadata)

    lining = Image.open(OUT/"sources/inner_skirt_plate.png").convert("RGBA")
    lining = lining.crop(lining.getchannel("A").point(lambda v:255 if v>64 else 0).getbbox())
    lining = lining.resize((258,59),Image.Resampling.LANCZOS)
    inner = canvas();inner.alpha_composite(lining,(344,735))
    save_part("skirt_inner",inner,metadata)
    front_body=section(native,542,1024)
    front_body.putalpha(ImageChops.multiply(front_body.getchannel("A"),ImageChops.invert(removal)))
    save_part("front_body_without_legs",front_body,metadata)
    unchanged=(np.asarray(removal)[542:]==0)
    checks["front_body_pixels_outside_leg_masks_changed"]=int((
        np.any(np.asarray(front_body)[542:]!=np.asarray(native)[542:],axis=2)&unchanged).sum())
    assert checks["front_body_pixels_outside_leg_masks_changed"]==0
    assert checks["l_visible_native_pixel_diff"]==checks["r_visible_native_pixel_diff"]==0

    # An actual static texture trial, not a claim of successful rig binding.
    # Keep all original character pixels in front, and feet/cuffs from the
    # native master. The generated pieces only complete hidden upper roots.
    under = canvas()
    for side in ("l","r"):
        under.alpha_composite(masters[side])
    under.alpha_composite(inner)
    preview=Image.alpha_composite(under,front_body)
    preview.alpha_composite(section(native,0,542))
    checks["scope"]="Static artwork registration only; no runtime mesh/pose validation."
    checks["visible_source"]="rig_repair.registered(front_armless_v1.png, .78, (31,28)), same as repair_layers"
    checks["source_sha256"]=hashlib.sha256((ROOT/"assets/art/rig_repair/front_armless_v1.png").read_bytes()).hexdigest()
    checks["coordinates"]={"knee_bone_guide_y":800,"native_skin_join_y":826,
        "visible_sock_frill_y":[839,861],"existing_ankle_bone_y":905,
        "actual_shoe_vamp_begins_y_approx":880}

    # Checkerboard parts board, plus a source-vs-trial identity comparison.
    font=ImageFont.truetype(FONT,22);small=ImageFont.truetype(FONT,17)
    board=checker((1160,820));d=ImageDraw.Draw(board)
    d.text((22,16),"站姿腿部补件 · 原袜 / 原鞋像素复用",font=font,fill="#162544")
    entries=[("左腿连续母件",masters["l"]), ("右腿连续母件",masters["r"]),
             ("左大腿（重叠拆件）",uppers["l"]), ("右小腿（重叠拆件）",section(masters["r"],780,917))]
    for i,(label,im) in enumerate(entries):
        x=20+i*280;part=im.crop(im.getchannel("A").getbbox())
        scale=min(2.1,230/part.width,500/part.height)
        part=part.resize((round(part.width*scale),round(part.height*scale)),Image.Resampling.NEAREST)
        board.alpha_composite(part,(x+20,85));d.text((x,55),label,font=small,fill="#162544")
    board.alpha_composite(lining.resize((516,118)),(30,635))
    d.text((30,605),"裙内衬（挂在现有前裙后、腿根前）",font=small,fill="#162544")
    d.text((600,620),"y=800 是膝骨参考，不是可见袜口",font=small,fill="#162544")
    d.text((600,652),"袜口花边实际约 y=839–861",font=small,fill="#162544")
    d.text((600,684),"连续母件优先；上下腿拆件仅供参考",font=small,fill="#162544")
    d.text((600,716),"未改生产 rig；屈膝 / 提踵仍待绑定回归",font=small,fill="#162544")
    board.convert("RGB").save(OUT/"parts-overview.jpg",quality=94)

    comparison=checker((1000,700));dc=ImageDraw.Draw(comparison)
    for i,(label,im) in enumerate((("原站姿纹理",native),("补件静态试装",preview))):
        dc.text((i*500+35,15),label,font=font,fill="#162544")
        crop=im.crop((350,700,600,960)).resize((500,520),Image.Resampling.NEAREST)
        comparison.alpha_composite(crop,(i*500,60))
    dc.text((25,610),"同画布、同坐标、1:1 局部贴图；不是动作验收图",font=font,fill="#162544")
    comparison.convert("RGB").save(OUT/"neutral-registration.jpg",quality=94)
    occlusion=checker((1140,430));od=ImageDraw.Draw(occlusion)
    for i,(label,lift) in enumerate((("中立",None),("左腿图层上移 8px","l"),("右腿图层上移 8px","r"))):
        sample=canvas()
        for side in ("l","r"):
            sample.alpha_composite(masters[side],(0,-8 if side==lift else 0))
        sample.alpha_composite(inner);sample.alpha_composite(front_body)
        piece=sample.crop((350,760,600,955)).resize((375,293),Image.Resampling.NEAREST)
        occlusion.alpha_composite(piece,(i*380,55))
        od.text((i*380+15,17),label,font=small,fill="#162544")
    od.text((20,370),"仅检查拆层 / 裙下遮挡；不是屈膝、接地或循环验收",font=font,fill="#162544")
    occlusion.convert("RGB").save(OUT/"occlusion-layer-check.jpg",quality=94)

    suggested_knees={}
    for side in ("l","r"):
        xs=np.where(np.asarray(masters[side])[800,:,3]>128)[0]
        suggested_knees[side]=[(int(xs[0])+int(xs[-1]))/2,800]
    manifest={"coordinate_system":"1024x1024 source pixels, x right/y down; no extra scaling",
        "runtime_status":"art kit only, not integrated", "parts":metadata,
        "bone_guides":{"hip_l":[442,720],"hip_r":[500,720],
                       "ankle_l":[432,905],"ankle_r":[520,905]},
        "suggested_new_knees_from_texture_y800":suggested_knees,
        "primary_attachment_plan":{"leg_slots":["leg_l_full","leg_r_full"],
            "shoe_slots":["shoe_l","shoe_r"],"continuous_master":["leg_l_master","leg_r_master"],
            "replace_body_before_old_cut_legs":"front_body_without_legs",
            "reference_only":["thigh_l","thigh_r","calf_l","calf_r","shoe_l_overlap_reference","shoe_r_overlap_reference",
                "thigh_l_painted_underlap","thigh_r_painted_underlap","source_leg_l_removal_mask","source_leg_r_removal_mask"],
            "layer_order_back_to_front":["legs_and_shoes","skirt_inner","existing_front_body_and_skirt"]}}
    (OUT/"assembly.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    checks["minimum_attachment_source_y"] = min(v["source_rect"][1] for v in metadata.values())
    (OUT/"validation.json").write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(checks,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
