$execute store result score #grid vm_state run data get storage vanilla_map:atlas config.levels[$(zoom)].grid
$execute store result score #pixel vm_state run data get storage vanilla_map:atlas config.levels[$(zoom)].pixel
$execute store result score #tile_w vm_state run data get storage vanilla_map:atlas config.levels[$(zoom)].width
$execute store result score #tile_h vm_state run data get storage vanilla_map:atlas config.levels[$(zoom)].height
execute store result score #atlas_x vm_state run data get storage vanilla_map:atlas config.x
execute store result score #atlas_z vm_state run data get storage vanilla_map:atlas config.z
