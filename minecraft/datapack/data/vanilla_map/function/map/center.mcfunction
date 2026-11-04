# Recenter on current player coordinates at the existing zoom level.
execute store result score #u vm_state run data get entity @s Pos[0] 1
execute store result score #v vm_state run data get entity @s Pos[2] 1
function vanilla_map:map/show_point
