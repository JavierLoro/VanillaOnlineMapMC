execute if entity @s[tag=vmp_open] run return run function vanilla_map_post:close
execute unless dimension minecraft:overworld run return run tellraw @s {"text":"The map covers the Overworld.","color":"yellow"}
scoreboard players add @s vmp_leaves 0
scoreboard players operation @s vmp_session = @s vmp_leaves
posteffect add @s vanilla_map_post:map
tag @s add vmp_open
