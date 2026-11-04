# Look at the outer border to move one tile in that direction.
scoreboard players set @s vm_pan 0
execute if score return_u floating_ui.temp matches ..-22000 run scoreboard players set @s vm_pan 1
execute if score return_u floating_ui.temp matches 22000.. run scoreboard players set @s vm_pan 2
execute if score return_v floating_ui.temp matches 12600.. run scoreboard players set @s vm_pan 3
execute if score return_v floating_ui.temp matches ..-12500 run scoreboard players set @s vm_pan 4
execute if score @s vm_pan matches 0 run return 0
scoreboard players set @s vm_cool 12
execute if score @s vm_pan matches 1 run scoreboard players remove @s vm_col 1
execute if score @s vm_pan matches 2 run scoreboard players add @s vm_col 1
execute if score @s vm_pan matches 3 run scoreboard players remove @s vm_row 1
execute if score @s vm_pan matches 4 run scoreboard players add @s vm_row 1
function vanilla_map:map/prepare
function vanilla_map:map/update
