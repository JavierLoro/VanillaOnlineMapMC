execute as @a[scores={vmd_action=97}] run dialog clear @s
scoreboard players reset @a[scores={vmd_action=98}] vmd_sector
execute as @a[scores={vmd_action=98..99}] at @s run function vanilla_map_dialog:show
execute as @a[scores={vmd_action=1..}] if score @s vmd_action <= #sectors vmd_calc at @s run function vanilla_map_dialog:select
scoreboard players set @a[scores={vmd_action=1..}] vmd_action 0
scoreboard players set @a[scores={vmd_action=..-1}] vmd_action 0
scoreboard players enable @a vmd_action
