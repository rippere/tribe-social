import { useEffect, useMemo, useState } from 'react'
import { ThreeCanvas } from '@remotion/three'
import { continueRender, delayRender, staticFile } from 'remotion'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

// Frame-driven port of apps/web/components/brain/CortexBrain.tsx (feat/cortex-render).
// Same mesh, same shader; the only change is that time comes from the Remotion
// frame instead of useFrame, so every rendered frame is deterministic.

const N_VERTS = 20484
const TEX = 144 // 144² = 20736 ≥ 20484

export interface ActivityMeta {
  frames: number
  vertices: number
  hz: number
  source: 'tribe' | 'illustrative'
  label: string
  note: string
}

export interface CortexAssets {
  geometry: THREE.BufferGeometry
  /** null until real TRIBE output has been exported; never placeholder data. */
  activity: { meta: ActivityMeta; data: Uint8Array } | null
}

export function useCortexAssets(): CortexAssets | null {
  const [assets, setAssets] = useState<CortexAssets | null>(null)
  const [handle] = useState(() => delayRender('cortex assets'))

  useEffect(() => {
    const geometry = new GLTFLoader()
      .loadAsync(staticFile('cortex/cortex.glb'))
      .then(gltf => {
        const mesh = (gltf.scene.getObjectByName('cortex') ?? gltf.scene.children[0]) as THREE.Mesh
        const g = mesh.geometry.clone()
        // GLTFLoader lower-cases custom attributes; give them shader-safe names.
        g.setAttribute('aSulc', g.getAttribute('_sulc'))
        g.setAttribute('aIdx', g.getAttribute('_fsa5_idx'))
        g.setAttribute('aW', g.getAttribute('_fsa5_w'))
        g.computeVertexNormals()
        g.center()
        // Normalise to a radius of 70 so the camera framing doesn't depend on mesh units.
        g.computeBoundingSphere()
        const k = 70 / (g.boundingSphere?.radius || 1)
        g.scale(k, k, k)
        return g
      })
    const activity = Promise.all([
      fetch(staticFile('cortex/activity.json')).then(r => (r.ok ? (r.json() as Promise<ActivityMeta>) : null)),
      fetch(staticFile('cortex/activity.bin')).then(r => (r.ok ? r.arrayBuffer() : null)),
    ])
      .then(([meta, buf]) => (meta && buf && meta.source === 'tribe' ? { meta, data: new Uint8Array(buf) } : null))
      .catch(() => null)

    Promise.all([geometry, activity])
      .then(([g, a]) => {
        setAssets({ geometry: g, activity: a })
        continueRender(handle)
      })
      .catch(err => {
        console.error('cortex assets failed to load', err)
        continueRender(handle)
      })
  }, [handle])

  return assets
}

const vertexShader = /* glsl */ `
  attribute float aSulc;
  attribute vec3 aIdx;
  attribute vec3 aW;
  uniform sampler2D uAct;
  varying float vAct;
  varying float vSulc;
  varying vec3 vNormal;
  varying vec3 vView;

  float act(float i) {
    int k = int(i + 0.5);
    return texelFetch(uAct, ivec2(k % ${TEX}, k / ${TEX}), 0).r;
  }

  void main() {
    vAct = dot(aW, vec3(act(aIdx.x), act(aIdx.y), act(aIdx.z)));
    vSulc = aSulc;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vView = -mv.xyz;
    gl_Position = projectionMatrix * mv;
  }
`

const fragmentShader = /* glsl */ `
  uniform float uThreshold;
  uniform float uIntensity;
  varying float vAct;
  varying float vSulc;
  varying vec3 vNormal;
  varying vec3 vView;

  vec3 ramp(float x) {
    vec3 deep = vec3(0.0, 0.34, 0.40);
    vec3 cyan = vec3(0.29, 0.85, 0.93);
    vec3 hot  = vec3(0.94, 0.99, 1.0);
    return x < 0.8 ? mix(deep, cyan, x / 0.8) : mix(cyan, hot, (x - 0.8) / 0.2 * 0.6);
  }

  void main() {
    vec3 n = normalize(vNormal);
    vec3 v = normalize(vView);
    vec3 l = normalize(vec3(0.35, 0.8, 0.6));
    float diffuse = 0.28 + 0.72 * max(dot(n, l), 0.0);
    float rim = pow(1.0 - max(dot(n, v), 0.0), 3.0);
    vec3 tissue = mix(vec3(0.36, 0.37, 0.40), vec3(0.11, 0.12, 0.14), vSulc);
    vec3 color = tissue * diffuse + rim * vec3(0.18, 0.22, 0.26);
    float a = clamp((vAct - uThreshold) / (1.0 - uThreshold), 0.0, 1.0) * uIntensity;
    vec3 glow = ramp(clamp(a, 0.0, 1.0));
    color = mix(color, glow * (0.55 + 0.45 * diffuse), smoothstep(0.0, 0.2, a));
    color += glow * a * 0.2;
    gl_FragColor = vec4(color, 1.0);
  }
`

interface CortexProps {
  assets: CortexAssets
  /** Clip time in seconds; TRIBE frames are 1 s apart and blended linearly. */
  t: number
  /** Rotation about the vertical axis in radians; π/2 shows the left lateral surface. */
  rotation: number
  width: number
  height: number
  /** 0 hides activation (the bare mesh), 1 shows it fully. */
  intensity?: number
}

export function Cortex({ assets, t, rotation, width, height, intensity = 1 }: CortexProps) {
  const texture = useMemo(() => {
    const tex = new THREE.DataTexture(new Float32Array(TEX * TEX), TEX, TEX, THREE.RedFormat, THREE.FloatType)
    tex.minFilter = THREE.NearestFilter
    tex.magFilter = THREE.NearestFilter
    return tex
  }, [])

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader,
        fragmentShader,
        uniforms: { uAct: { value: texture }, uThreshold: { value: 0.18 }, uIntensity: { value: intensity } },
      }),
    // intensity is pushed through the uniform below, not a rebuild
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [texture],
  )
  material.uniforms.uIntensity.value = intensity

  // Upload the activation for this exact frame (no clock, no useFrame).
  const out = texture.image.data as Float32Array
  const act = assets.activity
  if (act) {
    const { frames, hz } = act.meta
    const f = Math.max(0, Math.min(t * hz, frames - 1))
    const f0 = Math.floor(f)
    const f1 = Math.min(f0 + 1, frames - 1)
    const a = f - f0
    const d = act.data
    const o0 = f0 * N_VERTS
    const o1 = f1 * N_VERTS
    for (let i = 0; i < N_VERTS; i++) {
      out[i] = (d[o0 + i] + (d[o1 + i] - d[o0 + i]) * a - 128) / 127
    }
  } else {
    out.fill(0)
  }
  texture.needsUpdate = true

  return (
    <ThreeCanvas width={width} height={height} camera={{ position: [0, 0, 260], fov: 32, near: 1, far: 2000 }}>
      {/* Mesh is Y-up (x right, y superior, z posterior); spin about the vertical axis. */}
      <group rotation={[0.12, rotation, 0]}>
        <mesh geometry={assets.geometry} material={material} />
      </group>
    </ThreeCanvas>
  )
}
