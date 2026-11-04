execute if entity @s[tag=vm_close_requested] run return run function vanilla_map:map/close
execute unless dimension minecraft:overworld run return run function vanilla_map:map/close
execute if predicate vanilla_map:sneaking run return run function vanilla_map:map/close
execute if score @s vm_cool matches 1.. run scoreboard players remove @s vm_cool 1
scoreboard players operation #owner vm_state = @s floating_ui.uid
scoreboard players set #near vm_state 0
execute as @e[type=minecraft:item_display,tag=vm_root,distance=..8] if score @s floating_ui.uid = #owner vm_state run scoreboard players set #near vm_state 1
execute if score #near vm_state matches 0 run return run tag @s remove vm_opened
execute if score #draw vm_state matches 0 run function vanilla_map:map/markers
