scoreboard players operation #owner vm_state = @s floating_ui.uid
scoreboard players set #near vm_state 0
execute as @a[tag=vm_opened,distance=..8] if score @s floating_ui.uid = #owner vm_state run scoreboard players set #near vm_state 1
execute if score #near vm_state matches 0 run function floating_ui:_dispose_ui
