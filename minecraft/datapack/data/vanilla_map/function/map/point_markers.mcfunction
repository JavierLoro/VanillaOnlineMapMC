execute store result score #u vm_state run data get storage vanilla_map:work list[0].x
execute store result score #v vm_state run data get storage vanilla_map:work list[0].z
function vanilla_map:map/draw_marker
data remove storage vanilla_map:work list[0]
execute if data storage vanilla_map:work list[0] run function vanilla_map:map/point_markers
