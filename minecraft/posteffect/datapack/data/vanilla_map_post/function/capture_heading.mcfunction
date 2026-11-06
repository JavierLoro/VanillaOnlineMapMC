# Quantize the opening yaw to 64 directions, rounded and wrapped to 0..63.
scoreboard players operation @s vmp_heading = @s vmp_yaw
scoreboard players operation @s vmp_heading %= #full_turn vmp_pan
execute if score @s vmp_heading matches ..-1 run scoreboard players add @s vmp_heading 36000
scoreboard players operation @s vmp_heading *= #heading_steps vmp_pan
scoreboard players add @s vmp_heading 18000
scoreboard players operation @s vmp_heading /= #full_turn vmp_pan
scoreboard players operation @s vmp_heading %= #heading_steps vmp_pan
