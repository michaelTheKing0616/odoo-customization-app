import math, json
from shapely.geometry import LineString, Polygon, Point, box
from shapely.ops import unary_union
from shapely import affinity
from svgpathtools import parse_path

W = 1.0  # half stroke (2px Lucide stroke)
TILT = math.radians(15)

ICONS = {
 "model": [("p","M4 20V11a8 8 0 0 1 16 0v9"),("p","M4 20h16"),("p","M8 14h8"),("p","M8 17h8")],
 "field": [("rect",3,7,18,10,2),("p","M8 10v4"),("p","M12 12h5")],
 "view": [("rect",3,4,18,16,2),("p","M3 9h18"),("p","M9 20v-4a3 3 0 0 1 6 0v4")],
 "automation": [("p","M4 20v-7a8 8 0 0 1 16 0v7"),("p","M13 7l-3 6h4l-3 6")],
 "approval-rule": [("p","M5 21V11a7 7 0 0 1 14 0v10"),("p","M9 14l2 2 4-4")],
 "bridge-flow": [("circle",4,17,2),("circle",20,17,2),("p","M6 17a6 6 0 0 1 12 0"),("p","M12 11v6")],
 "numbering": [("p","M9 4 7 20"),("p","M17 4l-2 16"),("p","M4 9h16"),("p","M3 15h16")],
 "history": [("p","M3 12a9 9 0 1 0 2.64-6.36L3 8"),("p","M3 3v5h5"),("p","M12 7v5l3 2")],
}

def sample(d):
    out = []
    for sub in parse_path(d).continuous_subpaths():
        pts = []
        for seg in sub:
            n = 2 if seg.__class__.__name__ == "Line" else 24
            for i in range(n + 1):
                z = seg.point(i / n)
                if not pts or abs(pts[-1][0]-z.real)+abs(pts[-1][1]-z.imag) > 1e-6:
                    pts.append((z.real, z.imag))
        out.append(pts)
    return out

def cut_end(geom, p, q):
    """Square the end at p (q is the previous point), extended by W, then tilt the cut 15 degrees."""
    dx, dy = p[0]-q[0], p[1]-q[1]; L = math.hypot(dx, dy); ux, uy = dx/L, dy/L
    cx, cy = p[0] + ux*W, p[1] + uy*W
    # half-plane behind the cut line through (cx,cy), whose normal is u rotated by TILT
    nx = ux*math.cos(TILT) - uy*math.sin(TILT); ny = ux*math.sin(TILT) + uy*math.cos(TILT)
    tx, ty = -ny, nx; B = 50
    front = Polygon([(cx+tx*B, cy+ty*B), (cx-tx*B, cy-ty*B), (cx-tx*B+nx*B, cy-ty*B+ny*B), (cx+tx*B+nx*B, cy+ty*B+ny*B)])
    local = Point(p).buffer(2.2*W + 1.2)
    return geom.difference(front.intersection(local))

def open_stroke(pts):
    closed = math.hypot(pts[0][0]-pts[-1][0], pts[0][1]-pts[-1][1]) < 1e-3
    if closed:
        return Polygon(pts).exterior.buffer(W, join_style=1)
    a = pts[0]; b = pts[1]; y = pts[-1]; z = pts[-2]
    def ext(p, q, by):
        dx, dy = p[0]-q[0], p[1]-q[1]; L = math.hypot(dx, dy); return (p[0]+dx/L*by, p[1]+dy/L*by)
    line = LineString([ext(a, b, 2*W)] + pts + [ext(y, z, 2*W)])
    g = line.buffer(W, cap_style=2, join_style=1, quad_segs=8)
    g = cut_end(g, a, b)
    g = cut_end(g, y, z)
    return g

def elem(e):
    if e[0] == "p":
        return [open_stroke(s) for s in sample(e[1])]
    if e[0] == "rect":
        _, x, y, w, h, r = e
        shape = box(x+r, y+r, x+w-r, y+h-r).buffer(r, quad_segs=8)
        return [shape.exterior.buffer(W, join_style=1)]
    if e[0] == "circle":
        _, cx, cy, r = e
        return [Point(cx, cy).buffer(r, quad_segs=16).exterior.buffer(W)]

def to_d(g):
    polys = [g] if g.geom_type == "Polygon" else list(g.geoms)
    parts = []
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            c = list(ring.coords)[:-1]
            parts.append("M" + "L".join(f"{x:.2f} {y:.2f}" for x, y in c) + "Z")
    return "".join(parts)

out = {}
for name, els in ICONS.items():
    g = unary_union([x for e in els for x in elem(e)]).simplify(0.02)
    out[name] = to_d(g)
json.dump(out, open("paths.json", "w"))
print({k: len(v) for k, v in out.items()})
