$data modify storage vanilla_map_post:pan operation set value "$(operation)"
scoreboard players add @s vmp_heading 0
execute store result storage vanilla_map_post:pan heading int 1 run scoreboard players get @s vmp_heading
execute store result storage vanilla_map_post:pan x int 1 run scoreboard players get @s vmp_sent_x
execute store result storage vanilla_map_post:pan z int 1 run scoreboard players get @s vmp_sent_z
scoreboard players operation @s vmp_word = @s vmp_sent_x
scoreboard players operation @s vmp_digit = @s vmp_word
scoreboard players operation @s vmp_digit %= #radix vmp_pan
execute store result storage vanilla_map_post:pan d0 int 1 run scoreboard players get @s vmp_digit
scoreboard players operation @s vmp_word /= #radix vmp_pan
scoreboard players operation @s vmp_digit = @s vmp_word
scoreboard players operation @s vmp_digit %= #radix vmp_pan
execute store result storage vanilla_map_post:pan d1 int 1 run scoreboard players get @s vmp_digit
scoreboard players operation @s vmp_word /= #radix vmp_pan
scoreboard players operation @s vmp_digit = @s vmp_word
scoreboard players operation @s vmp_digit %= #radix vmp_pan
execute store result storage vanilla_map_post:pan d2 int 1 run scoreboard players get @s vmp_digit
scoreboard players operation @s vmp_word /= #radix vmp_pan
scoreboard players operation @s vmp_digit = @s vmp_word
scoreboard players operation @s vmp_digit %= #radix vmp_pan
execute store result storage vanilla_map_post:pan d3 int 1 run scoreboard players get @s vmp_digit
scoreboard players operation @s vmp_word /= #radix vmp_pan
scoreboard players operation @s vmp_word = @s vmp_sent_z
scoreboard players operation @s vmp_digit = @s vmp_word
scoreboard players operation @s vmp_digit %= #radix vmp_pan
execute store result storage vanilla_map_post:pan d4 int 1 run scoreboard players get @s vmp_digit
scoreboard players operation @s vmp_word /= #radix vmp_pan
scoreboard players operation @s vmp_digit = @s vmp_word
scoreboard players operation @s vmp_digit %= #radix vmp_pan
execute store result storage vanilla_map_post:pan d5 int 1 run scoreboard players get @s vmp_digit
scoreboard players operation @s vmp_word /= #radix vmp_pan
scoreboard players operation @s vmp_digit = @s vmp_word
scoreboard players operation @s vmp_digit %= #radix vmp_pan
execute store result storage vanilla_map_post:pan d6 int 1 run scoreboard players get @s vmp_digit
scoreboard players operation @s vmp_word /= #radix vmp_pan
scoreboard players operation @s vmp_digit = @s vmp_word
scoreboard players operation @s vmp_digit %= #radix vmp_pan
execute store result storage vanilla_map_post:pan d7 int 1 run scoreboard players get @s vmp_digit
scoreboard players operation @s vmp_word /= #radix vmp_pan
function vanilla_map_post:pan_effects with storage vanilla_map_post:pan
