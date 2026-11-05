$data modify storage vanilla_map_post:pan operation set value "$(operation)"
execute store result storage vanilla_map_post:pan x int 1 run scoreboard players get @s vmp_sent_x
execute store result storage vanilla_map_post:pan z int 1 run scoreboard players get @s vmp_sent_z
function vanilla_map_post:pan_effects with storage vanilla_map_post:pan
