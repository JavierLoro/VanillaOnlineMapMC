scoreboard players set @s vm_open 0
execute unless dimension minecraft:overworld run return run tellraw @s {"text":"The world map covers the Overworld.","color":"yellow"}
execute unless function floating_ui:util/check/world_entity run return run tellraw @s {"text":"Map controls are still starting. Try again in a moment.","color":"yellow"}
execute unless score @s floating_ui.uid matches 0.. run function floating_ui:util/player_uid
execute if entity @s[tag=vm_opened] run function vanilla_map:map/close
scoreboard players set @s vm_zoom 0
scoreboard players set @s vm_col 0
scoreboard players set @s vm_row 0
scoreboard players set @s vm_pan 0
scoreboard players set @s vm_cool 8
scoreboard players set @s vm_index -1
scoreboard players reset @s vm_pin_x
scoreboard players reset @s vm_pin_z
data modify storage vanilla_map:work args.uuid set from entity @s UUID
function vanilla_map:points/ensure with storage vanilla_map:work args
data modify storage floating_ui:input data set value {type:"button",tag:"vm_surface",size:[4.8f,2.7f],item:{id:"minecraft:paper"},model:"vanilla_map:view/0/0/0",display:"none",rotation:[0f,0f,0f,1f],left_click:"vanilla_map:input/left",right_click:"vanilla_map:input/right",roll:"vanilla_map:input/roll",move:"vanilla_map:input/move",move_in:"vanilla_map:input/move"}
tag @s add vm_opening
function floating_ui:.player_new_ui
execute as @e[type=minecraft:item_display,tag=vm_surface,distance=..8] if score @s floating_ui.uid = @p[tag=vm_opening] floating_ui.uid on vehicle run tag @s add vm_root
scoreboard players operation #owner vm_state = @s floating_ui.uid
scoreboard players set #near vm_state 0
execute as @e[type=minecraft:item_display,tag=vm_root,distance=..8] if score @s floating_ui.uid = #owner vm_state run scoreboard players set #near vm_state 1
execute if score #near vm_state matches 1 run tag @s add vm_opened
tag @s remove vm_opening
execute if entity @s[tag=vm_opened] run title @s actionbar {"text":"Look around • Wheel: zoom • Right click: center • Sneak: close","color":"white"}
