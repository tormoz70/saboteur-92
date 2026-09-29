shader_type canvas_item;

void fragment() {
	vec2 uv = UV - vec2(0.5);
	float vignette = smoothstep(0.42, 0.92, length(uv));
	COLOR = vec4(0.01, 0.02, 0.05, vignette * 0.42);
}
