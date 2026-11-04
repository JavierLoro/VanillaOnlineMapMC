scoreboard players operation #button vm_state = return_u floating_ui.temp
scoreboard players operation #button vm_state += #half_w vm_state
scoreboard players operation #button vm_state /= #button_w vm_state
execute if score #button vm_state matches 0 run return run function vanilla_map:input/button_zoom {direction:-1}
execute if score #button vm_state matches 1 run return run function vanilla_map:input/button_zoom {direction:1}
execute if score #button vm_state matches 2 run return run function vanilla_map:map/center
execute if score #button vm_state matches 3 run return run function vanilla_map:points/save_here
execute if score #button vm_state matches 4 run return run function vanilla_map:points/save_pin
execute if score #button vm_state matches 5 run return run function vanilla_map:points/next
execute if score #button vm_state matches 6 run return run function vanilla_map:points/delete
execute if score #button vm_state matches 7.. run tag @s add vm_close_requested
