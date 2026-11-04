function vanilla_map:map/prepare
function vanilla_map:map/tile_origin
scoreboard players operation #viewer vm_state = @s floating_ui.uid
function vanilla_map:points/load
data modify storage vanilla_map:work marker.color set value [1.0f,0.62f,0.05f]
execute if data storage vanilla_map:work list[0] run function vanilla_map:map/point_markers
data modify storage vanilla_map:work marker.color set value [0.4f,0.9f,1.0f]
execute if score @s vm_pin_x matches -30000000..30000000 run scoreboard players operation #u vm_state = @s vm_pin_x
execute if score @s vm_pin_x matches -30000000..30000000 run scoreboard players operation #v vm_state = @s vm_pin_z
execute if score @s vm_pin_x matches -30000000..30000000 run function vanilla_map:map/draw_marker
data modify storage vanilla_map:work marker.color set value [1.0f,1.0f,1.0f]
execute store result score #u vm_state run data get entity @s Pos[0] 1
execute store result score #v vm_state run data get entity @s Pos[2] 1
function vanilla_map:map/draw_marker
