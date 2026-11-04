execute as @p[tag=floating_ui_owner,tag=vm_opened] at @s if score slot floating_ui.temp matches ..-1 run function vanilla_map:input/zoom {direction:1}
execute as @p[tag=floating_ui_owner,tag=vm_opened] at @s if score slot floating_ui.temp matches 1.. run function vanilla_map:input/zoom {direction:-1}
