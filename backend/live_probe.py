"""Build an opt-in, loaded-chunk streaming experiment for vanilla clients."""

from collections import defaultdict
import json

if __package__:
    from .extract_surface import SURFACE_COLORS, material_color
    from .map_colors import BLOCK_COLORS
else:
    from extract_surface import SURFACE_COLORS, material_color
    from map_colors import BLOCK_COLORS


PACKET_BYTES = 20
FIRST_PIXEL = 10
PIXELS_PER_PACKET = 4
HOLD_TICKS = 4


def encode_packet(cx, cz, group, colors, revision):
    """Reference encoder; Fletcher-16 rejects most partially applied effect lists."""
    if not (-32768 <= cx <= 32767 and -32768 <= cz <= 32767):
        raise ValueError("Probe chunk coordinates must fit signed 16 bits")
    if not 0 <= group < 64 or not 0 <= revision <= 255 or len(colors) != 4:
        raise ValueError("Invalid probe packet")
    data = [*(cx + 32768).to_bytes(2, "big"), *(cz + 32768).to_bytes(2, "big"), group]
    for color in colors:
        if len(color) != 3 or any(not isinstance(v, int) or not 0 <= v <= 255 for v in color):
            raise ValueError("Expected four RGB byte triples")
        data.extend(color)
    data.append(revision)
    a = b = 0
    for value in data:
        a = (a + value) % 255
        b = (b + a) % 255
    return data + [a, b]


def shader(source, root):
    source = source.replace("uniform sampler2D StateSampler;",
                            "uniform sampler2D StateSampler;\nuniform sampler2D LiveSampler;")
    source = source.replace("vec2 StateSize;", "vec2 StateSize;\n    vec2 LiveSize;")
    source = source.replace("\nvoid main() {", "\n" + (root / "live_overlay.glsl").read_text() + "\nvoid main() {")
    return source.replace("    color = playerMarker(",
                          "    color = liveOverlay(color, camera + playerOffset + vec2(MapOrigin.xz), texCoord, OutSize);\n"
                          "    color = playerMarker(")


def resources(pack, root, namespace):
    assets = f"assets/{namespace}"
    for slot in range(PACKET_BYTES):
        for value in range(256):
            effect = {"passes": [{
                "vertex_shader": f"{namespace}:post/pan_signal",
                "fragment_shader": f"{namespace}:post/pan_signal",
                "output": "minecraft:main",
                "uniforms": {"PanSignal": [{"name": "Signal", "type": "vec2",
                                             "value": [FIRST_PIXEL + slot, value]}]},
            }]}
            pack.writestr(f"{assets}/post_effect/live/byte/{slot}_{value}.json", json.dumps(effect))
    effect = {
        "targets": {"history": {"width": 16, "height": 17, "persistent": True},
                    "next": {"width": 16, "height": 17}},
        "passes": [
            {"vertex_shader": "minecraft:core/screenquad", "fragment_shader": f"{namespace}:post/live_cache",
             "inputs": [{"sampler_name": "Main", "target": "minecraft:main"},
                        {"sampler_name": "Previous", "target": "history"}], "output": "next"},
            {"vertex_shader": "minecraft:core/screenquad", "fragment_shader": "minecraft:post/blit",
             "inputs": [{"sampler_name": "In", "target": "next"}], "output": "history",
             "uniforms": {"BlitConfig": [{"name": "ColorModulate", "type": "vec4", "value": [1, 1, 1, 1]}]}},
            {"vertex_shader": f"{namespace}:post/live_stamp", "fragment_shader": f"{namespace}:post/live_stamp",
             "inputs": [{"sampler_name": "In", "target": "next"}], "output": "minecraft:main"},
        ],
    }
    # Separate chains own separate histories. The surviving bank forwards its
    # complete cache when the other bank is removed/reinserted after new writers.
    for bank in range(2):
        pack.writestr(f"{assets}/post_effect/live/bank{bank}.json", json.dumps(effect))
    for name in ("live_cache.fsh", "live_stamp.vsh", "live_stamp.fsh"):
        pack.write(root / name, f"{assets}/shaders/post/{name}")


def lifecycle(name, content):
    if name == "load.mcfunction":
        objectives = ["vmp_live", "vmp_lmode", "vmp_ltimer", "vmp_lindex", "vmp_lbank",
                      "vmp_lsent", "vmp_lgen", "vmp_lcx", "vmp_lcz", "vmp_lx", "vmp_lz",
                      "vmp_lr", "vmp_lg", "vmp_lb", "vmp_lword", "vmp_la", "vmp_lsum",
                      "vmp_lid", "vmp_lresume", "vmp_lload", "vmp_lcache"]
        objectives += [f"vmp_lold{i}" for i in range(PACKET_BYTES)]
        prefix = "".join(f"scoreboard objectives add {obj} {'trigger' if obj == 'vmp_live' else 'dummy'}\n"
                         for obj in objectives)
        constants = {"#byte": 256, "#sum": 255, "#chunk": 16, "#two": 2, "#one": 1,
                     "#hold": HOLD_TICKS, "#four": 4}
        prefix += "".join(f"scoreboard players set {key} vmp_lword {value}\n" for key, value in constants.items())
        prefix += "scoreboard players add #next_id vmp_lid 0\n"
        return prefix + content
    if name == "toggle.mcfunction":
        return content + (
            "\nexecute unless score @s vmp_lresume matches 0..1 if score @s vmp_lmode matches 1..2 run scoreboard players set @s vmp_lresume 1\n"
            "execute if score @s vmp_lresume matches 1 run function vanilla_map_post:live/resume\n")
    if name == "close.mcfunction":
        return "execute if entity @s[tag=vmp_live] run function vanilla_map_post:live/stop\n" + content
    if name == "tick.mcfunction":
        return content + (
            "\nexecute as @a[scores={vmp_live=1..}] at @s run function vanilla_map_post:live/trigger\n"
            "scoreboard players set @a[scores={vmp_live=1..}] vmp_live 0\n"
            "scoreboard players set @a[scores={vmp_live=..-1}] vmp_live 0\n"
            "scoreboard players enable @a vmp_live\n"
            "execute as @a[tag=vmp_live,tag=vmp_open] at @s run function vanilla_map_post:live/tick\n")
    return content


def datapack(pack, namespace):
    prefix = f"data/{namespace}/function/live/"
    def function(name, lines):
        if not isinstance(lines, str):
            lines = "\n".join(lines) + "\n"
        pack.writestr(prefix + name + ".mcfunction", lines)

    function("trigger", [
        "execute if score @s vmp_live matches 3.. run return run function vanilla_map_post:live/disable",
        'execute unless entity @s[tag=vmp_open] run return run tellraw @s {"text":"Open the map first.","color":"yellow"}',
        "execute if entity @s[tag=vmp_live] run function vanilla_map_post:live/stop",
        "scoreboard players operation @s vmp_lmode = @s vmp_live",
        "execute store result score @s vmp_lcx run data get entity @s Pos[0] 0.0625",
        "execute store result score @s vmp_lcz run data get entity @s Pos[2] 0.0625",
        'execute unless score @s vmp_lcx matches -32768..32767 run return run tellraw @s {"text":"Outside the probe coordinate range.","color":"red"}',
        'execute unless score @s vmp_lcz matches -32768..32767 run return run tellraw @s {"text":"Outside the probe coordinate range.","color":"red"}',
        "scoreboard players add @s vmp_lgen 1",
        "scoreboard players operation @s vmp_lgen %= #byte vmp_lword",
        "function vanilla_map_post:live/cache/context",
        "function vanilla_map_post:live/cache/create with storage vanilla_map_post:live context",
        "scoreboard players set @s vmp_lresume 1",
        "function vanilla_map_post:live/start",
    ])
    function("start", [
        "scoreboard players set @s vmp_lindex 0",
        "scoreboard players set @s vmp_lbank 0",
        "scoreboard players set @s vmp_lsent 0",
        "scoreboard players set @s vmp_ltimer 0",
        "tag @s add vmp_live",
        "posteffect add @s vanilla_map_post:live/bank0",
        "posteffect add @s vanilla_map_post:live/bank1",
        "function vanilla_map_post:live/next",
    ])
    function("disable", [
        "scoreboard players set @s vmp_lresume 0",
        "function vanilla_map_post:live/stop",
    ])
    function("resume", [
        "function vanilla_map_post:live/cache/context",
        "function vanilla_map_post:live/cache/ensure with storage vanilla_map_post:live context",
        "function vanilla_map_post:live/cache/restore with storage vanilla_map_post:live context",
        "function vanilla_map_post:live/start",
    ])
    function("cache/context", [
        "execute unless score @s vmp_lid matches 1.. run function vanilla_map_post:live/cache/assign_id",
        *(f"execute store result storage vanilla_map_post:live context.{key} int 1 run scoreboard players get @s {score}"
          for key, score in (("id", "vmp_lid"), ("index", "vmp_lindex"), ("cx", "vmp_lcx"),
                             ("cz", "vmp_lcz"), ("mode", "vmp_lmode"), ("revision", "vmp_lgen"))),
    ])
    function("cache/assign_id", [
        "scoreboard players add #next_id vmp_lid 1",
        "scoreboard players operation @s vmp_lid = #next_id vmp_lid",
    ])
    function("cache/create", [
        "$data modify storage vanilla_map_post:live_cache players.p$(id) set value {version:1,cx:$(cx),cz:$(cz),mode:$(mode),revision:$(revision),packets:{}}",
    ])
    function("cache/ensure", [
        "$execute unless data storage vanilla_map_post:live_cache players.p$(id){version:1} run function vanilla_map_post:live/cache/create with storage vanilla_map_post:live context",
    ])
    function("cache/restore", [
        *(f"$execute store result score @s {score} run data get storage vanilla_map_post:live_cache players.p$(id).{field}"
          for score, field in (("vmp_lcx", "cx"), ("vmp_lcz", "cz"), ("vmp_lmode", "mode"), ("vmp_lgen", "revision"))),
    ])
    function("cache/save_packet", [
        "$data modify storage vanilla_map_post:live_cache players.p$(id).packets.g$(index) set from storage vanilla_map_post:live packet",
    ])
    function("cache/load_packet", [
        "$execute unless data storage vanilla_map_post:live_cache players.p$(id).packets.g$(index).b19 run return 0",
        "$data modify storage vanilla_map_post:live packet set from storage vanilla_map_post:live_cache players.p$(id).packets.g$(index)",
        "return 1",
    ])
    function("cache/check_loaded", [
        "$execute if loaded $(x) 0 $(z) run return 1",
        "return 0",
    ])
    function("tick", [
        "scoreboard players add @s vmp_ltimer 1",
        "execute if score @s vmp_ltimer >= #hold vmp_lword run function vanilla_map_post:live/next",
    ])
    function("stop", [
        "execute if score @s vmp_lsent matches 1 run function vanilla_map_post:live/remove",
        "posteffect remove @s vanilla_map_post:live/bank0",
        "posteffect remove @s vanilla_map_post:live/bank1",
        "scoreboard players set @s vmp_lsent 0",
        "tag @s remove vmp_live",
    ])
    function("remove", [
        *(f"execute store result storage vanilla_map_post:live last.b{i} int 1 run scoreboard players get @s vmp_lold{i}"
          for i in range(PACKET_BYTES)),
        "function vanilla_map_post:live/remove_bytes with storage vanilla_map_post:live last",
    ])
    function("remove_bytes", [f"$posteffect remove @s vanilla_map_post:live/byte/{i}_$(b{i})" for i in range(PACKET_BYTES)])
    function("emit", [line for i in range(PACKET_BYTES) for line in (
        f"$scoreboard players set @s vmp_lold{i} $(b{i})",
        f"$posteffect add @s vanilla_map_post:live/byte/{i}_$(b{i})")])
    function("receiver", [
        "$posteffect remove @s vanilla_map_post:live/bank$(bank)",
        "$posteffect add @s vanilla_map_post:live/bank$(bank)",
    ])
    function("read_column", [
        "$execute unless loaded $(x) 0 $(z) run return 0",
        "$execute positioned $(x) 0 $(z) positioned over world_surface positioned ~ ~-1 ~ run function vanilla_map_post:live/sample",
    ])
    function("checker", [
        "scoreboard players operation @s vmp_lword = @s vmp_lx",
        "scoreboard players operation @s vmp_lword += @s vmp_lz",
        "scoreboard players operation @s vmp_lword %= #two vmp_lword",
        "scoreboard players set @s vmp_lr 240",
        "scoreboard players set @s vmp_lg 50",
        "scoreboard players set @s vmp_lb 70",
        "execute if score @s vmp_lword matches 0 run scoreboard players set @s vmp_lr 30",
        "execute if score @s vmp_lword matches 0 run scoreboard players set @s vmp_lg 210",
        "execute if score @s vmp_lword matches 0 run scoreboard players set @s vmp_lb 230",
    ])
    function("next", [
        "scoreboard players set @s vmp_ltimer 0",
        "function vanilla_map_post:live/cache/context",
        "scoreboard players operation @s vmp_lword = @s vmp_lcx",
        "scoreboard players operation @s vmp_lword *= #chunk vmp_lword",
        "execute store result storage vanilla_map_post:live context.x int 1 run scoreboard players get @s vmp_lword",
        "scoreboard players operation @s vmp_lword = @s vmp_lcz",
        "scoreboard players operation @s vmp_lword *= #chunk vmp_lword",
        "execute store result storage vanilla_map_post:live context.z int 1 run scoreboard players get @s vmp_lword",
        "execute store result score @s vmp_lload run function vanilla_map_post:live/cache/check_loaded with storage vanilla_map_post:live context",
        "scoreboard players set @s vmp_lcache 0",
        "execute if score @s vmp_lmode matches 2 run scoreboard players set @s vmp_lload 1",
        "execute if score @s vmp_lload matches 1 run function vanilla_map_post:live/sample_packet",
        "execute if score @s vmp_lload matches 0 store result score @s vmp_lcache run function vanilla_map_post:live/cache/load_packet with storage vanilla_map_post:live context",
        "execute if score @s vmp_lload matches 1 run function vanilla_map_post:live/send_current",
        "execute if score @s vmp_lload matches 0 if score @s vmp_lcache matches 1 run function vanilla_map_post:live/send_current",
        "scoreboard players add @s vmp_lindex 1",
        "execute if score @s vmp_lindex matches 64.. run scoreboard players set @s vmp_lindex 0",
    ])
    lines = ["data modify storage vanilla_map_post:live packet set value {}"]
    for coordinate, slot in (("vmp_lcx", 0), ("vmp_lcz", 2)):
        lines += [f"scoreboard players operation @s vmp_lword = @s {coordinate}",
                  "scoreboard players add @s vmp_lword 32768",
                  "scoreboard players operation @s vmp_lword /= #byte vmp_lword",
                  f"execute store result storage vanilla_map_post:live packet.b{slot} int 1 run scoreboard players get @s vmp_lword",
                  f"scoreboard players operation @s vmp_lword = @s {coordinate}",
                  "scoreboard players add @s vmp_lword 32768",
                  "scoreboard players operation @s vmp_lword %= #byte vmp_lword",
                  f"execute store result storage vanilla_map_post:live packet.b{slot + 1} int 1 run scoreboard players get @s vmp_lword"]
    lines += ["execute store result storage vanilla_map_post:live packet.b4 int 1 run scoreboard players get @s vmp_lindex",
              "execute store result storage vanilla_map_post:live packet.b17 int 1 run scoreboard players get @s vmp_lgen",
              "scoreboard players operation @s vmp_lx = @s vmp_lindex",
              "scoreboard players operation @s vmp_lx %= #four vmp_lword",
              "scoreboard players operation @s vmp_lx *= #four vmp_lword",
              "scoreboard players operation @s vmp_lz = @s vmp_lindex",
              "scoreboard players operation @s vmp_lz /= #four vmp_lword"]
    for pixel in range(4):
        lines += ["scoreboard players operation @s vmp_lword = @s vmp_lcx",
                  "scoreboard players operation @s vmp_lword *= #chunk vmp_lword",
                  "scoreboard players operation @s vmp_lword += @s vmp_lx",
                  "execute store result storage vanilla_map_post:live context.x int 1 run scoreboard players get @s vmp_lword",
                  "scoreboard players operation @s vmp_lword = @s vmp_lcz",
                  "scoreboard players operation @s vmp_lword *= #chunk vmp_lword",
                  "scoreboard players operation @s vmp_lword += @s vmp_lz",
                  "execute store result storage vanilla_map_post:live context.z int 1 run scoreboard players get @s vmp_lword",
                  *(f"scoreboard players set @s vmp_l{channel} 106" for channel in ("r", "g", "b")),
                  "execute if score @s vmp_lmode matches 1 run function vanilla_map_post:live/read_column with storage vanilla_map_post:live context",
                  "execute if score @s vmp_lmode matches 2 run function vanilla_map_post:live/checker",
                  *(f"execute store result storage vanilla_map_post:live packet.b{5 + pixel * 3 + c} int 1 run scoreboard players get @s vmp_l{channel}"
                    for c, channel in enumerate(("r", "g", "b"))),
                  "scoreboard players add @s vmp_lx 1"]
    lines += ["scoreboard players set @s vmp_la 0", "scoreboard players set @s vmp_lsum 0"]
    for i in range(18):
        lines += [f"execute store result score @s vmp_lword run data get storage vanilla_map_post:live packet.b{i}",
                  "scoreboard players operation @s vmp_la += @s vmp_lword",
                  "scoreboard players operation @s vmp_la %= #sum vmp_lword",
                  "scoreboard players operation @s vmp_lsum += @s vmp_la",
                  "scoreboard players operation @s vmp_lsum %= #sum vmp_lword"]
    lines += ["execute store result storage vanilla_map_post:live packet.b18 int 1 run scoreboard players get @s vmp_la",
              "execute store result storage vanilla_map_post:live packet.b19 int 1 run scoreboard players get @s vmp_lsum",
              "function vanilla_map_post:live/cache/save_packet with storage vanilla_map_post:live context"]
    function("sample_packet", lines)
    function("send_current", [
              "execute if score @s vmp_lsent matches 1 run function vanilla_map_post:live/remove",
              "function vanilla_map_post:live/emit with storage vanilla_map_post:live packet",
              "execute store result storage vanilla_map_post:live context.bank int 1 run scoreboard players get @s vmp_lbank",
              "function vanilla_map_post:live/receiver with storage vanilla_map_post:live context",
              "scoreboard players operation @s vmp_lword = #one vmp_lword",
              "scoreboard players operation @s vmp_lword -= @s vmp_lbank",
              "scoreboard players operation @s vmp_lbank = @s vmp_lword",
              "function vanilla_map_post:clear_view",
              *(f"execute if score @s vmp_zoom matches {i} run posteffect add @s vanilla_map_post:{name}"
                for i, name in enumerate(("map_far", "map", "map_near", "map_close"))),
              "scoreboard players set @s vmp_lsent 1"])

    groups = defaultdict(list)
    names = set(BLOCK_COLORS) | {"minecraft:" + name for name in SURFACE_COLORS}
    for name in sorted(names):
        color = material_color(name)
        if color:
            groups[color].append(name)
    colors = sorted(groups)
    def tag(name, blocks):
        pack.writestr(f"data/{namespace}/tags/block/live/{name}.json", json.dumps({
            "values": [{"id": block, "required": False} for block in blocks]}))
    tag("known", [name for color in colors for name in groups[color]])
    function("sample", [
        "execute if block ~ ~ ~ #vanilla_map_post:live/known run return run function vanilla_map_post:live/palette/root",
    ])
    def tree(subset, name):
        if len(subset) == 1:
            rgb = bytes.fromhex(subset[0][1:])
            function("palette/" + name, [f"scoreboard players set @s vmp_l{channel} {value}"
                                        for channel, value in zip(("r", "g", "b"), rgb)])
            return
        middle = len(subset) // 2
        left, right = name + "0", name + "1"
        tag(left, [block for color in subset[:middle] for block in groups[color]])
        function("palette/" + name, [
            f"execute if block ~ ~ ~ #vanilla_map_post:live/{left} run return run function vanilla_map_post:live/palette/{left}",
            f"return run function vanilla_map_post:live/palette/{right}"])
        tree(subset[:middle], left)
        tree(subset[middle:], right)
    tree(colors, "root")
