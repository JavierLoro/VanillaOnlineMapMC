execute as @a[tag=vmp_open] unless score @s vmp_leaves = @s vmp_session run function vanilla_map_post:close
execute as @a[tag=vmp_open] at @s unless dimension minecraft:overworld run function vanilla_map_post:close
execute as @a[scores={vmp_map=1}] at @s run function vanilla_map_post:toggle
execute as @a[tag=vmp_open] at @s run function vanilla_map_post:update_view
scoreboard players set @a[scores={vmp_map=1..}] vmp_map 0
scoreboard players set @a[scores={vmp_map=..-1}] vmp_map 0
scoreboard players enable @a vmp_map
