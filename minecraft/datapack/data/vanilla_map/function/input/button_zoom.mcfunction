# The toolbar is outside the useful map content; zoom around the view center.
scoreboard players set return_u floating_ui.temp 0
scoreboard players set return_v floating_ui.temp 0
$function vanilla_map:input/zoom {direction:$(direction)}
