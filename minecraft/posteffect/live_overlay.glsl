vec3 liveOverlay(vec3 color, vec2 worldPosition, vec2 uv, vec2 outSize) {
    if (LiveSize.x < 30.0 || LiveSize.y < 19.0) return color;
    vec4 magic = round(texelFetch(LiveSampler, ivec2(2, 18), 0) * 255.0);
    vec4 meta = round(texelFetch(LiveSampler, ivec2(1, 18), 0) * 255.0);
    if (any(notEqual(magic, vec4(83, 84, 49, 255))) ||
        any(notEqual(meta.gba, vec3(76, 86, 255)))) return color;
    vec4 origin = round(texelFetch(LiveSampler, ivec2(0, 18), 0) * 255.0);
    vec2 corner = (vec2(origin.r * 256.0 + origin.g, origin.b * 256.0 + origin.a) - 32768.0) * 16.0;
    vec2 local = floor(worldPosition) - corner;
    if (all(greaterThanEqual(local, vec2(0))) && all(lessThan(local, vec2(16)))) {
        vec4 pixel = texelFetch(LiveSampler, ivec2(local) + ivec2(0, 2), 0);
        color = mix(color, pixel.rgb, pixel.a);
    }
    // A north-up enlarged view makes a single 16-block chunk readable at every zoom.
    float scale = clamp(floor(min(outSize.x, outSize.y) / 80.0), 2.0, 12.0);
    vec2 preview = vec2(uv.x * outSize.x - (outSize.x - 20.0 - scale * 16.0),
                        (1.0 - uv.y) * outSize.y - 20.0) / scale;
    if (all(greaterThanEqual(preview, vec2(-0.3))) && all(lessThan(preview, vec2(16.3)))) {
        color = vec3(0.08, 0.11, 0.14);
        if (all(greaterThanEqual(preview, vec2(0))) && all(lessThan(preview, vec2(16)))) {
            vec4 pixel = texelFetch(LiveSampler, ivec2(preview) + ivec2(0, 2), 0);
            color = mix(color, pixel.rgb, pixel.a);
        }
    }
    return color;
}
