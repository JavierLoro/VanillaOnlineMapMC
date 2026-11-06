vec3 playerMarker(vec3 color, vec2 playerOffset, float pixelsPerBlock) {
    vec2 pixel = playerOffset * pixelsPerBlock;
    if (any(greaterThan(abs(pixel), vec2(36.0)))) {
        return color;
    }
    // The timestamp pixel's alpha stores the heading captured on map opening.
    float encoded = round(texelFetch(StateSampler, ivec2(1, 0), 0).a * 255.0);
    if (encoded < 128.0 || encoded > 191.0) {
        return color;
    }
    float yaw = (encoded - 128.0) * 6.28318530718 / 64.0;
    vec2 direction = vec2(-sin(yaw), cos(yaw));
    float forward = dot(pixel, direction);
    float side = abs(dot(pixel, vec2(-direction.y, direction.x)));
    // A pointed arrow with an inset tail, measured in screen pixels.
    float outer = (32.0 - forward - side * (42.0 / 13.0)) / sqrt(1.0 + pow(42.0 / 13.0, 2.0));
    float tail = (forward + 4.0 + side * (6.0 / 13.0)) / sqrt(1.0 + pow(6.0 / 13.0, 2.0));
    float edge = min(outer, tail);
    float coverage = smoothstep(-0.5, 0.5, edge);
    vec3 arrow = mix(vec3(0.035, 0.06, 0.09), vec3(0.35, 0.85, 1.0), smoothstep(0.6, 1.6, edge));
    return mix(color, arrow, coverage);
}
