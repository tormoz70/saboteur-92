shader_type canvas_item;

// The title sprite is a solid black silhouette. Fill it light and trace a
// thin rim so it reads on the dark menu.

void fragment() {
	vec4 body = texture(TEXTURE, UV);
	vec2 p = TEXTURE_PIXEL_SIZE;
	float near = texture(TEXTURE, UV + vec2(p.x, 0.0)).a
		+ texture(TEXTURE, UV - vec2(p.x, 0.0)).a
		+ texture(TEXTURE, UV + vec2(0.0, p.y)).a
		+ texture(TEXTURE, UV - vec2(0.0, p.y)).a;
	if (body.a > 0.5) {
		COLOR = vec4(0.94, 0.96, 0.98, 1.0);
	} else if (near > 0.5) {
		COLOR = vec4(0.45, 0.82, 1.0, 0.9);
	} else {
		COLOR = vec4(0.0);
	}
}
