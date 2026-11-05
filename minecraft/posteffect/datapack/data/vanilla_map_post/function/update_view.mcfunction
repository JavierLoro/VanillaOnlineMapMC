execute store result score @s vmp_pan run function vanilla_map_post:update_pan
execute store result score @s vmp_scroll run function vanilla_map_post:update_zoom
execute if score @s vmp_pan matches 0 if score @s vmp_scroll matches 0 run return 0

# Place the map renderer after both pixel writers in the player's effect list.
function vanilla_map_post:clear_view
execute if score @s vmp_zoom matches 0 run posteffect add @s vanilla_map_post:map_far
execute if score @s vmp_zoom matches 1 run posteffect add @s vanilla_map_post:map
execute if score @s vmp_zoom matches 2 run posteffect add @s vanilla_map_post:map_near
