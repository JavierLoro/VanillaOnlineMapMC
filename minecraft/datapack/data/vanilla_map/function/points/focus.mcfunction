$execute store result score #u vm_state run data get storage vanilla_map:work list[$(index)].x
$execute store result score #v vm_state run data get storage vanilla_map:work list[$(index)].z
title @s actionbar {"text":"Saved point · X ","extra":[{"score":{"name":"#u","objective":"vm_state"}}," · Z ",{"score":{"name":"#v","objective":"vm_state"}}]}
scoreboard players operation @s vm_pin_x = #u vm_state
scoreboard players operation @s vm_pin_z = #v vm_state
function vanilla_map:map/show_point
