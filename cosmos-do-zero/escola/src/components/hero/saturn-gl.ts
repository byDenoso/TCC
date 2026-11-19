import { vertex, fragment } from './saturn-shader';

export type SaturnPaint = { paint: (degrees: number, longitude?: number) => void; dispose: () => void };

export async function mountSaturn(
  canvas: HTMLCanvasElement,
  gl: WebGLRenderingContext,
  mapUrl: string
): Promise<SaturnPaint | null> {
  const image = new Image();
  image.src = mapUrl;
  await image.decode();
  const program = gl.createProgram();
  if (!program) return null;
  const shaders: WebGLShader[] = [];
  for (const [type, code] of [
    [gl.VERTEX_SHADER, vertex],
    [gl.FRAGMENT_SHADER, fragment],
  ] as const) {
    const shader = gl.createShader(type);
    if (!shader) return null;
    shaders.push(shader);
    gl.shaderSource(shader, code);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS))
      throw new Error(gl.getShaderInfoLog(shader) || 'Shader de Saturno inválido');
    gl.attachShader(program, shader);
  }
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS))
    throw new Error(gl.getProgramInfoLog(program) || 'Cena de Saturno indisponível');
  gl.useProgram(program);
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const corner = gl.getAttribLocation(program, 'corner');
  gl.enableVertexAttribArray(corner);
  gl.vertexAttribPointer(corner, 2, gl.FLOAT, false, 0, 0);
  const texture = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, image);
  const elevation = gl.getUniformLocation(program, 'elevation');
  const rotation = gl.getUniformLocation(program, 'longitude');
  const size = gl.getUniformLocation(program, 'size');
  gl.uniform1i(gl.getUniformLocation(program, 'surfaceMap'), 0);
  const paint = (degrees: number, lon = 0.45) => {
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniform2f(size, canvas.width, canvas.height);
    gl.uniform1f(elevation, degrees);
    gl.uniform1f(rotation, lon);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  };
  const dispose = () => {
    gl.deleteTexture(texture);
    gl.deleteBuffer(buffer);
    for (const shader of shaders) gl.deleteShader(shader);
    gl.deleteProgram(program);
  };
  return { paint, dispose };
}
