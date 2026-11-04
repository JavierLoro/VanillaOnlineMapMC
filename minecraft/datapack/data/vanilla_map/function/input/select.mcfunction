execute if score return_v floating_ui.temp matches 10125..12562 run return run function vanilla_map:input/toolbar
scoreboard players set @s vm_index -1
function vanilla_map:map/prepare
function vanilla_map:map/project_click
scoreboard players operation @s vm_pin_x = #u vm_state
scoreboard players operation @s vm_pin_z = #v vm_state
title @s actionbar {"text":"Selected X ","extra":[{"score":{"name":"@s","objective":"vm_pin_x"}}," · Z ",{"score":{"name":"@s","objective":"vm_pin_z"}}]}
