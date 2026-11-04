scoreboard players add #draw vm_state 1
execute if score #draw vm_state matches 4.. run scoreboard players set #draw vm_state 0
scoreboard players enable @a vm_open
execute as @a[scores={vm_open=1}] at @s run function vanilla_map:map/open
scoreboard players set @a[scores={vm_open=..-1}] vm_open 0
scoreboard players set @a[scores={vm_open=2..}] vm_open 0
execute as @a[tag=vm_opened] at @s run function vanilla_map:map/player_tick
execute in minecraft:overworld as @e[type=minecraft:item_display,tag=vm_root] at @s run function vanilla_map:map/check_owner
