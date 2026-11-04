$execute if data storage vanilla_map:points owners[{uuid:$(uuid)}].points[{x:$(x),z:$(z),dimension:"minecraft:overworld"}] run return run title @s actionbar {"text":"This point is already saved.","color":"yellow"}
$data modify storage vanilla_map:points owners[{uuid:$(uuid)}].points append value {x:$(x),z:$(z),dimension:"minecraft:overworld"}
scoreboard players operation @s vm_index = #count vm_state
title @s actionbar {"text":"Map point saved.","color":"green"}
