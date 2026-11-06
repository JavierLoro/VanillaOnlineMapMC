execute if entity @s[tag=vmp_open] run return run function vanilla_map_post:close
execute unless dimension minecraft:overworld run return run tellraw @s {"text":"The map covers the Overworld.","color":"yellow"}
scoreboard players add @s vmp_leaves 0
scoreboard players operation @s vmp_session = @s vmp_leaves
execute store result score @s vmp_slot run data get entity @s SelectedItemSlot
scoreboard players set @s vmp_zoom 2
execute store result score @s vmp_yaw run data get entity @s Rotation[0] 100
function vanilla_map_post:capture_heading
execute store result score @s vmp_pitch run data get entity @s Rotation[1] 100
scoreboard players set @s vmp_x 3276700
scoreboard players set @s vmp_z 3276700
scoreboard players set @s vmp_sent_x 32767
scoreboard players set @s vmp_sent_z 32767
function vanilla_map_post:set_pan_effects {operation:"add"}
posteffect add @s vanilla_map_post:map_near
tag @s add vmp_open
