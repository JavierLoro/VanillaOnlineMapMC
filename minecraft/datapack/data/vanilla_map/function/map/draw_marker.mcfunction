scoreboard players operation #u vm_state -= #view_x vm_state
scoreboard players operation #v vm_state -= #view_z vm_state
execute if score #u vm_state matches ..-1 run return 0
execute if score #v vm_state matches ..-1 run return 0
execute if score #u vm_state >= #tile_w vm_state run return 0
execute if score #v vm_state >= #tile_h vm_state run return 0
scoreboard players operation #u vm_state /= #pixel vm_state
scoreboard players operation #u vm_state *= #panel_w vm_state
scoreboard players operation #u vm_state /= #width vm_state
scoreboard players operation #u vm_state -= #half_w vm_state
scoreboard players operation #v vm_state /= #pixel vm_state
scoreboard players operation #v vm_state *= #panel_h vm_state
scoreboard players operation #v vm_state /= #height vm_state
scoreboard players operation #v vm_state -= #half_h vm_state
execute store result storage vanilla_map:work marker.x double 0.0001 run scoreboard players get #u vm_state
execute store result storage vanilla_map:work marker.y double -0.0001 run scoreboard players get #v vm_state
tag @s add vm_viewer
execute as @e[type=minecraft:item_display,tag=vm_root,distance=..8] if score @s floating_ui.uid = #viewer vm_state at @s run function vanilla_map:map/particle with storage vanilla_map:work marker
tag @s remove vm_viewer
