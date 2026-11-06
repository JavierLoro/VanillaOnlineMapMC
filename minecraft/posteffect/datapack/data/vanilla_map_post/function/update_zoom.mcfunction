scoreboard players operation @s vmp_scroll = @s vmp_slot
execute store result score @s vmp_slot run data get entity @s SelectedItemSlot
execute if score @s vmp_slot = @s vmp_scroll run return 0
scoreboard players operation @s vmp_scroll -= @s vmp_slot

# Interpret the hotbar as a ring. Scrolling up selects the previous slot.
execute if score @s vmp_scroll matches 5.. run scoreboard players remove @s vmp_scroll 9
execute if score @s vmp_scroll matches ..-5 run scoreboard players add @s vmp_scroll 9
execute if score @s vmp_scroll matches 1.. if score @s vmp_zoom matches 3 run return 0
execute if score @s vmp_scroll matches ..-1 if score @s vmp_zoom matches 0 run return 0
execute if score @s vmp_scroll matches 1.. run scoreboard players add @s vmp_zoom 1
execute if score @s vmp_scroll matches ..-1 run scoreboard players remove @s vmp_zoom 1
return 1
