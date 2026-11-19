'use client';

import { useEffect, useId, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import type { SaturnPaint } from './saturn-gl';

const initialAngle = 24;
const snapAngle = (degrees: number) => Math.max(12, Math.min(44, Math.round(degrees / 4) * 4));

export default function HeroSky({
  assetRoot = `${process.env.NEXT_PUBLIC_BASE_PATH || ''}/cosmos-hero`,
}: {
  assetRoot?: string;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const drawing = useRef<SaturnPaint | null>(null);
  const requestedGpu = useRef(false);
  const mounted = useRef(false);
  const target = useRef(initialAngle);
  const displayed = useRef(initialAngle);
  const frame = useRef(0);
  const dragging = useRef<{ id: number; x: number; degrees: number } | null>(null);
  const updateView = useRef<() => void>(() => {});
  const id = useId();
  const [degrees, setDegrees] = useState(initialAngle);
  const [ready, setReady] = useState(false);
  const [live, setLive] = useState(false);

  useEffect(() => {
    mounted.current = true;
    setReady(true);
    const surface = canvas.current;
    if (!surface) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    const size = () => {
      if (!drawing.current) return;
      const width = Math.max(
        1,
        Math.min(1500, Math.round(surface.clientWidth * Math.min(1.4, window.devicePixelRatio || 1)))
      );
      surface.width = width;
      surface.height = Math.round(width * 0.56);
      drawing.current.paint(displayed.current);
    };
    const render = () => {
      const renderer = drawing.current;
      if (!renderer) return;
      if (frame.current) cancelAnimationFrame(frame.current);
      // Ray tracing runs on demand. The poster covers idle and reduced-motion views.
      const start = performance.now();
      const from = displayed.current;
      const until = target.current;
      const tick = (now: number) => {
        const elapsed = Math.min(1, (now - start) / 220);
        const eased = 1 - Math.pow(1 - elapsed, 3);
        displayed.current = from + (until - from) * eased;
        renderer.paint(displayed.current);
        if (elapsed < 1) frame.current = requestAnimationFrame(tick);
        else frame.current = 0;
      };
      if (reduced.matches || from === until) {
        displayed.current = until;
        renderer.paint(until);
        frame.current = 0;
      } else frame.current = requestAnimationFrame(tick);
    };
    updateView.current = () => {
      if (drawing.current) {
        render();
        return;
      }
      if (requestedGpu.current || reduced.matches || navigator.hardwareConcurrency <= 2) return;
      requestedGpu.current = true;
      import('./saturn-gl')
        .then(async ({ mountSaturn }) => {
          const scene = await mountSaturn(surface, `${assetRoot}/saturno-mapa.webp`);
          if (!mounted.current) {
            scene?.dispose();
            return;
          }
          if (!scene) return;
          drawing.current = scene;
          displayed.current = target.current;
          size();
          setLive(true);
        })
        .catch(() => {
          /* Pre-rendered viewpoints remain interactive. */
        });
    };
    const observer = new ResizeObserver(size);
    observer.observe(surface);
    const lost = () => {
      cancelAnimationFrame(frame.current);
      frame.current = 0;
      drawing.current = null;
      setLive(false);
    };
    surface.addEventListener('webglcontextlost', lost);
    return () => {
      mounted.current = false;
      observer.disconnect();
      surface.removeEventListener('webglcontextlost', lost);
      cancelAnimationFrame(frame.current);
      drawing.current?.dispose();
      drawing.current = null;
      requestedGpu.current = false;
      updateView.current = () => {};
    };
  }, [assetRoot]);

  function change(deg: number) {
    const next = snapAngle(deg);
    if (next === target.current) return;
    target.current = next;
    setDegrees(next);
    updateView.current();
  }
  function move(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragging.current;
    if (drag?.id === event.pointerId) {
      change(drag.degrees + (event.clientX - drag.x) * 0.14);
      return;
    }
    if (event.pointerType !== 'mouse') return;
    const bounds = event.currentTarget.getBoundingClientRect();
    panel.current?.style.setProperty(
      '--sky-x',
      `${(event.clientX - bounds.left - bounds.width * 0.5) * 0.012}px`
    );
    panel.current?.style.setProperty(
      '--sky-y',
      `${(event.clientY - bounds.top - bounds.height * 0.5) * 0.012}px`
    );
  }
  function down(event: ReactPointerEvent<HTMLDivElement>) {
    if (!event.isPrimary || event.button !== 0) return;
    dragging.current = { id: event.pointerId, x: event.clientX, degrees: target.current };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  const poster = `${assetRoot}/saturno-${live ? initialAngle : degrees}.webp`;
  return (
    <div ref={panel} className="cosmos-sky" data-view={degrees}>
      <div
        className="cosmos-sky__stars"
        aria-hidden="true"
        style={{ backgroundImage: `url("${assetRoot}/campo-estelar.webp")` }}
      />
      <div
        className="cosmos-sky__world"
        onPointerDown={down}
        onPointerMove={move}
        onPointerLeave={() => {
          panel.current?.style.removeProperty('--sky-x');
          panel.current?.style.removeProperty('--sky-y');
        }}
        onPointerUp={() => {
          dragging.current = null;
        }}
        onPointerCancel={() => {
          dragging.current = null;
        }}
      >
        <picture>
          {(live || degrees === initialAngle) && (
            <source media="(max-width: 700px)" srcSet={`${assetRoot}/saturno-24-small.webp`} />
          )}
          <img
            src={poster}
            alt="Ilustração de Saturno. As faixas do planeta projetam-se por trás dos anéis, inclinados em relação à linha de visão."
            width={1440}
            height={806}
            fetchPriority="high"
            decoding="async"
            draggable={false}
          />
        </picture>
        <canvas
          ref={canvas}
          className={live ? 'cosmos-sky__canvas cosmos-sky__canvas--live' : 'cosmos-sky__canvas'}
          aria-hidden="true"
        />
      </div>
      {ready && (
        <div className="cosmos-sky__instrument">
          <label
            htmlFor={id}
            title="Arraste Saturno ou use as setas no controle para mudar o ângulo de visão"
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="5.2" />
              <ellipse cx="12" cy="12" rx="10.5" ry="3.1" transform="rotate(-25 12 12)" />
            </svg>
            <span>Inclinação dos anéis</span>
          </label>
          <input
            id={id}
            type="range"
            aria-valuetext={`${degrees} graus em relação ao plano dos anéis`}
            min="12"
            max="44"
            step="4"
            value={degrees}
            onChange={(e) => change(Number(e.target.value))}
          />
          <output htmlFor={id}>{degrees}°</output>
        </div>
      )}
    </div>
  );
}
