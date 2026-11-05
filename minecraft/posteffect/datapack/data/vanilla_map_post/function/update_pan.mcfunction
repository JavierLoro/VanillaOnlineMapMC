execute store result score @s vmp_dx run data get entity @s Rotation[0] 100
execute store result score @s vmp_dz run data get entity @s Rotation[1] 100
scoreboard players operation @s vmp_dx -= @s vmp_yaw
scoreboard players operation @s vmp_dz -= @s vmp_pitch
scoreboard players operation @s vmp_yaw += @s vmp_dx
scoreboard players operation @s vmp_pitch += @s vmp_dz

# Use the shortest yaw change across the -180/180 degree seam.
execute if score @s vmp_dx matches 18001.. run scoreboard players remove @s vmp_dx 36000
execute if score @s vmp_dx matches ..-18001 run scoreboard players add @s vmp_dx 36000
scoreboard players operation @s vmp_dx *= #sensitivity vmp_pan
scoreboard players operation @s vmp_dz *= #sensitivity vmp_pan
scoreboard players operation @s vmp_x += @s vmp_dx
scoreboard players operation @s vmp_z += @s vmp_dz
execute if score @s vmp_x matches ..-1 run scoreboard players set @s vmp_x 0
execute if score @s vmp_x matches 6553401.. run scoreboard players set @s vmp_x 6553400
execute if score @s vmp_z matches ..-1 run scoreboard players set @s vmp_z 0
execute if score @s vmp_z matches 6553401.. run scoreboard players set @s vmp_z 6553400

# Reset pitch near its limits so vertical panning can continue.
execute if score @s vmp_pitch matches ..-8500 run function vanilla_map_post:reset_pitch
execute if score @s vmp_pitch matches 8500.. run function vanilla_map_post:reset_pitch

# Round to a 16-bit coordinate without losing accumulated sub-step movement.
scoreboard players operation @s vmp_dx = @s vmp_x
scoreboard players operation @s vmp_dz = @s vmp_z
scoreboard players add @s vmp_dx 50
scoreboard players add @s vmp_dz 50
scoreboard players operation @s vmp_dx /= #pan_step vmp_pan
scoreboard players operation @s vmp_dz /= #pan_step vmp_pan
execute if score @s vmp_dx = @s vmp_sent_x if score @s vmp_dz = @s vmp_sent_z run return 0

function vanilla_map_post:set_pan_effects {operation:"remove"}
scoreboard players operation @s vmp_sent_x = @s vmp_dx
scoreboard players operation @s vmp_sent_z = @s vmp_dz
function vanilla_map_post:set_pan_effects {operation:"add"}
return 1
