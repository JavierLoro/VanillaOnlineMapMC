tag @s remove vm_close_requested
scoreboard players operation #owner vm_state = @s floating_ui.uid
execute in minecraft:overworld as @e[type=minecraft:item_display,tag=vm_root] if score @s floating_ui.uid = #owner vm_state at @s run function floating_ui:_dispose_ui
tag @s remove vm_opened
