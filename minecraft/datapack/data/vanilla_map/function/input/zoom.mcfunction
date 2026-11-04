function vanilla_map:map/prepare
function vanilla_map:map/project_click
$scoreboard players set #delta vm_state $(direction)
scoreboard players operation @s vm_zoom += #delta vm_state
scoreboard players operation @s vm_zoom > #zero vm_state
scoreboard players operation @s vm_zoom < #two vm_state
function vanilla_map:map/show_point
