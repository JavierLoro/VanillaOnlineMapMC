"""Exercise a generated probe datapack on an isolated official Java 26.3 server.

Usage: python tests/validate_live_probe_server.py --jar /path/server.jar
       --datapack /path/vanilla-map-post-datapack.zip --directory /fresh/test
Uses a private loopback port, a synthetic flat world and stdin; no RCON needed.
"""

import argparse
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.extract_surface import material_color
from backend.live_probe import encode_packet


def validate(jar, datapack, directory, java="java", port=25566):
    directory.mkdir(parents=True, exist_ok=False)
    packs = directory / "world/datapacks"
    packs.mkdir(parents=True)
    shutil.copy2(datapack, packs / "live-probe.zip")
    # Reuse bundled dependencies when available without copying the live world.
    for name in ("libraries", "versions"):
        source = jar.parent / name
        if source.is_dir():
            (directory / name).symlink_to(source, target_is_directory=True)
    (directory / "eula.txt").write_text("eula=true\n")
    (directory / "server.properties").write_text(
        f"server-ip=127.0.0.1\nserver-port={port}\nonline-mode=false\nlevel-name=world\n"
        'level-type=minecraft:flat\ngenerator-settings={"layers":[{"block":"minecraft:bedrock","height":1},'
        '{"block":"minecraft:dirt","height":2},{"block":"minecraft:grass_block","height":1}],'
        '"biome":"minecraft:plains"}\nview-distance=2\nsimulation-distance=2\nspawn-protection=0\n'
        'initial-enabled-packs=vanilla,file/live-probe.zip\nmanagement-server-enabled=false\nenable-rcon=false\n')
    log_path = directory / "validation.log"
    log = log_path.open("w", encoding="utf-8")
    launch = [java, "-Xms128M", "-Xmx768M", "-jar", str(jar), "--nogui"]
    process = subprocess.Popen(launch,
                               cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1)
    output = queue.Queue()
    def read():
        for line in process.stdout:
            log.write(line)
            log.flush()
            output.put(line)
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    def wait_for(predicate, seconds=60):
        deadline = time.monotonic() + seconds
        recent = []
        while time.monotonic() < deadline:
            try:
                line = output.get(timeout=0.5)
            except queue.Empty:
                if process.poll() is not None:
                    raise RuntimeError("Server exited; inspect validation.log")
                continue
            recent.append(line)
            if predicate(line):
                return line
        raise RuntimeError("Server response timed out: " + "".join(recent[-8:]))
    def command(text):
        process.stdin.write(text + "\n")
        process.stdin.flush()
    def payload():
        command("data get storage vanilla_map_post:live packet")
        line = wait_for(lambda text: "contents" in text and "b19:" in text)
        fields = {int(k): int(v) for k, v in re.findall(r"b(\d+): (-?\d+)", line)}
        return [fields[i] for i in range(20)]
    try:
        wait_for(lambda line: "Done (" in line, 90)
        command("forceload add -32 -16 -17 -1")
        wait_for(lambda line: "force" in line.lower() and "chunk" in line.lower(), 10)
        time.sleep(2)
        command("fill -32 80 -16 -17 80 -1 minecraft:gold_block")
        wait_for(lambda line: "Successfully filled" in line, 15)
        command('summon minecraft:marker -31 100 -15 {Tags:["vmp_probe","vmp_open"]}')
        command("scoreboard players set @e[tag=vmp_probe] vmp_live 1")
        command("execute as @e[tag=vmp_probe] at @s run function vanilla_map_post:live/trigger")
        gold = tuple(bytes.fromhex(material_color("minecraft:gold_block")[1:]))
        assert payload() == encode_packet(-2, -1, 0, [gold] * 4, 1)
        command("setblock -32 80 -16 minecraft:red_concrete")
        command("scoreboard players set @e[tag=vmp_probe] vmp_lindex 0")
        command("execute as @e[tag=vmp_probe] at @s run function vanilla_map_post:live/next")
        red = tuple(bytes.fromhex(material_color("minecraft:red_concrete")[1:]))
        assert payload() == encode_packet(-2, -1, 0, [red, gold, gold, gold], 1)
        command("execute as @e[tag=vmp_probe] at @s run debug function vanilla_map_post:live/next")
        profile = wait_for(lambda line: "Traced" in line and "command(s)" in line, 15)
        print(profile.strip(), flush=True)
        command("scoreboard players set @e[tag=vmp_probe] vmp_lmode 2")
        command("scoreboard players set @e[tag=vmp_probe] vmp_lindex 0")
        command("execute as @e[tag=vmp_probe] at @s run function vanilla_map_post:live/next")
        assert payload() == encode_packet(-2, -1, 0, [(30, 210, 230), (240, 50, 70)] * 2, 1)
        print("Minecraft 26.3: negative origin, live surface, changed block and checker packets match reference.", flush=True)
        command("scoreboard players set @e[tag=vmp_probe] vmp_lmode 1")
        command("scoreboard players set @e[tag=vmp_probe] vmp_lindex 0")
        command("execute as @e[tag=vmp_probe] at @s run function vanilla_map_post:live/next")
        saved = payload()
        command("execute as @e[tag=vmp_probe] run function vanilla_map_post:live/stop")
        command("stop")
        process.wait(timeout=30)
        reader.join(timeout=5)
        output = queue.Queue()
        process = subprocess.Popen(launch, cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, bufsize=1)
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        wait_for(lambda line: "Done (" in line, 90)
        # These coordinates are deliberately unloaded: the packet must come from
        # command storage saved by the prior server process, not a fresh sample.
        command("scoreboard players set @e[tag=vmp_probe] vmp_lcx 20000")
        command("scoreboard players set @e[tag=vmp_probe] vmp_lcz 20000")
        command("scoreboard players set @e[tag=vmp_probe] vmp_lindex 0")
        command("execute as @e[tag=vmp_probe] at @s run function vanilla_map_post:live/next")
        assert payload() == saved
        command("execute as @e[tag=vmp_probe] at @s run function vanilla_map_post:live/resume")
        assert payload() == saved
        print("Saved chunk packet survives a clean server restart, replays without loaded terrain and resumes the original origin.", flush=True)
    finally:
        if process.poll() is None:
            command("stop")
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        reader.join(timeout=5)
        log.close()
    errors = [line for line in log_path.read_text().splitlines() if "/ERROR]" in line]
    if errors or process.returncode:
        raise RuntimeError(f"Server exit {process.returncode}; errors: {errors}")
    print("Isolated server stopped cleanly, no loading errors.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--datapack", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--java", default="java")
    parser.add_argument("--port", type=int, default=25566)
    args = parser.parse_args()
    validate(args.jar.resolve(), args.datapack.resolve(), args.directory.resolve(), args.java, args.port)
