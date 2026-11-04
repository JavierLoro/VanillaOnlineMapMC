function vanilla_map:points/load
execute store result score #count vm_state run data get storage vanilla_map:work list
execute if score #count vm_state matches 0 run return run title @s actionbar {"text":"No saved points yet.","color":"yellow"}
scoreboard players add @s vm_index 1
execute if score @s vm_index >= #count vm_state run scoreboard players set @s vm_index 0
execute store result storage vanilla_map:work args.index int 1 run scoreboard players get @s vm_index
function vanilla_map:points/focus with storage vanilla_map:work args
