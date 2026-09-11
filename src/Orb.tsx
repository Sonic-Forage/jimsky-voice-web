import { useEffect, useRef } from 'react'
import * as THREE from 'three'

/**
 * The reactive orb. A point cloud on a sphere, displaced by the agent's state, with the accent
 * colour from settings. It is decoration with a job: you can read "listening / thinking /
 * speaking" across a room, which is the whole point of a kitchen screen.
 *
 * Falls back to nothing if WebGL is unavailable (headless browsers, locked-down devices) so the
 * caller's CSS orb takes over rather than leaving a black rectangle.
 */
export default function Orb({ state, accent = 'teal', size = 190 }: {
  state: string
  accent?: string
  size?: number
}) {
  const hostRef = useRef<HTMLDivElement>(null)
  const stateRef = useRef(state)
  stateRef.current = state

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' })
    } catch {
      return   // no WebGL: leave it to CSS
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(size, size)
    host.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100)
    camera.position.z = 3.4

    const palette: Record<string, [number, number]> = {
      teal: [0x4be3c8, 0xff5d8f],
      magenta: [0xff5d8f, 0xffc857],
      amber: [0xffc857, 0x4be3c8],
    }
    const [c1, c2] = palette[accent] ?? palette.teal

    const count = 4200
    const positions = new Float32Array(count * 3)
    const colors = new Float32Array(count * 3)
    const base = new Float32Array(count)
    const a = new THREE.Color(c1)
    const b = new THREE.Color(c2)
    for (let i = 0; i < count; i++) {
      const phi = Math.acos(1 - 2 * ((i + 0.5) / count))
      const theta = Math.PI * (1 + Math.sqrt(5)) * i
      const r = 1
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = r * Math.cos(phi)
      positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta)
      base[i] = r
      const mix = (i / count + Math.random() * 0.2) % 1
      const col = a.clone().lerp(b, mix)
      colors[i * 3] = col.r; colors[i * 3 + 1] = col.g; colors[i * 3 + 2] = col.b
    }
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3))

    const mat = new THREE.PointsMaterial({
      size: 0.022, vertexColors: true, transparent: true, opacity: 0.95,
      blending: THREE.AdditiveBlending, depthWrite: false,
    })
    const points = new THREE.Points(geo, mat)
    scene.add(points)

    const wire = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.16, 1),
      new THREE.MeshBasicMaterial({ color: c1, wireframe: true, transparent: true, opacity: 0.07 }),
    )
    scene.add(wire)

    let raf = 0
    let t = 0
    const clock = new THREE.Clock()
    const render = () => {
      raf = requestAnimationFrame(render)
      const dt = Math.min(clock.getDelta(), 0.05)
      t += dt
      const st = stateRef.current
      const energy = st === 'speaking' ? 1.0 : st === 'thinking' ? 0.55 : st === 'listening' ? 0.3 : 0.12
      const speed = st === 'speaking' ? 2.6 : st === 'thinking' ? 1.5 : 0.5
      const pos = geo.attributes.position as THREE.BufferAttribute
      const arr = pos.array as Float32Array
      for (let i = 0; i < count; i++) {
        const i3 = i * 3
        const nx = arr[i3], ny = arr[i3 + 1], nz = arr[i3 + 2]
        const len = Math.hypot(nx, ny, nz) || 1
        const wave = Math.sin(t * speed + base[i] * 9 + i * 0.02) * 0.5 + 0.5
        const r = 1 + energy * 0.16 * wave
        arr[i3] = (nx / len) * r
        arr[i3 + 1] = (ny / len) * r
        arr[i3 + 2] = (nz / len) * r
      }
      pos.needsUpdate = true
      points.rotation.y += dt * (0.1 + energy * 0.25)
      wire.rotation.y -= dt * 0.06
      renderer.render(scene, camera)
    }
    render()

    return () => {
      cancelAnimationFrame(raf)
      renderer.dispose()
      geo.dispose()
      mat.dispose()
      host.removeChild(renderer.domElement)
    }
  }, [accent, size])

  return <div className="orb-host" ref={hostRef} style={{ width: size, height: size }} />
}
