shader_type canvas_item;

// Nina is a solid black silhouette, so she vanishes against the black inside
// of a bookcase. The Spectrum drew a sprite there in the cell's ink colour;
// this traces that ink around her while she is behind one.
uniform float ink_on = 0.0;
uniform vec4 ink_color : source_color = vec4(0.0, 1.0, 0.0, 1.0);

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	if (c.a > 0.5) {
		COLOR = c;
	} else if (ink_on > 0.5) {
		vec2 p = TEXTURE_PIXEL_SIZE;
		float n = texture(TEXTURE, UV + vec2(p.x, 0.0)).a
			+ texture(TEXTURE, UV - vec2(p.x, 0.0)).a
			+ texture(TEXTURE, UV + vec2(0.0, p.y)).a
			+ texture(TEXTURE, UV - vec2(0.0, p.y)).a;
		COLOR = n > 0.5 ? ink_color : vec4(0.0);
	} else {
		COLOR = vec4(0.0);
	}
}
