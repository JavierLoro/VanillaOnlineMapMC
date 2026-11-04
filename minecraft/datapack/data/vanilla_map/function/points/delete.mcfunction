execute unless score @s vm_index matches 0.. run return run title @s actionbar {"text":"Select a saved point with My points first.","color":"yellow"}
data modify storage vanilla_map:work args.uuid set from entity @s UUID
execute store result storage vanilla_map:work args.index int 1 run scoreboard players get @s vm_index
function vanilla_map:points/remove with storage vanilla_map:work args
