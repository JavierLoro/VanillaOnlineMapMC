scoreboard players operation #last vm_state = #grid vm_state
scoreboard players remove #last vm_state 1
scoreboard players operation @s vm_col > #zero vm_state
scoreboard players operation @s vm_col < #last vm_state
scoreboard players operation @s vm_row > #zero vm_state
scoreboard players operation @s vm_row < #last vm_state
execute store result storage vanilla_map:work args.column int 1 run scoreboard players get @s vm_col
execute store result storage vanilla_map:work args.row int 1 run scoreboard players get @s vm_row
scoreboard players operation #owner vm_state = @s floating_ui.uid
execute as @e[type=minecraft:item_display,tag=vm_surface,distance=..8] if score @s floating_ui.uid = #owner vm_state run function vanilla_map:map/texture with storage vanilla_map:work args
