function vanilla_map:points/load
execute store result score #count vm_state run data get storage vanilla_map:work list
execute if score #count vm_state matches 16.. run return run title @s actionbar {"text":"You can save up to 16 points.","color":"yellow"}
execute store result storage vanilla_map:work args.x int 1 run scoreboard players get #u vm_state
execute store result storage vanilla_map:work args.z int 1 run scoreboard players get #v vm_state
function vanilla_map:points/append with storage vanilla_map:work args
