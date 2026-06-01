'use client';

import s from './LoadingScreen.module.css';

export function LoadingScreen() {
  return (
    <div className={s.overlay} aria-hidden="true">
      <div className={s.dotGrid} />
      <div className={s.colorWash} />
      <div className={s.vignette} />

      <div className={s.scene}>
        {/* Laser descending from top */}
        <div className={s.laserWrap}>
          <div className={s.laserBeam} />
        </div>

        {/* Diamond */}
        <div className={s.diamondWrap}>
          <svg
            width="220"
            height="280"
            viewBox="0 0 220 280"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <g className={s.diamondG}>
              {/* Crown — table */}
              <polygon className={s.fTable} points="78,42 142,42 164,80 56,80"     stroke="#7070a8" strokeWidth="1.2" />
              {/* Crown — main left / right */}
              <polygon className={s.fCL}    points="78,42 56,80 22,118 44,118"     stroke="#8080b0" strokeWidth="1.0" />
              <polygon className={s.fCR}    points="142,42 164,80 198,118 176,118" stroke="#8080b0" strokeWidth="1.0" />
              {/* Crown — corner facets */}
              <polygon className={s.fCCL}   points="56,80 22,118 66,118"           stroke="#9090b8" strokeWidth="0.9" />
              <polygon className={s.fCCR}   points="164,80 198,118 154,118"        stroke="#9090b8" strokeWidth="0.9" />
              <polygon className={s.fCCL}   points="56,80 66,118 110,100"          stroke="#9898c0" strokeWidth="0.8" />
              <polygon className={s.fCCR}   points="164,80 154,118 110,100"        stroke="#9898c0" strokeWidth="0.8" />
              {/* Star facets */}
              <polygon className={s.fTable} points="78,42 56,80 110,100"           stroke="#7878a8" strokeWidth="0.7" fill="rgba(228,228,252,0.5)" />
              <polygon className={s.fTable} points="142,42 164,80 110,100"         stroke="#7878a8" strokeWidth="0.7" fill="rgba(228,228,252,0.5)" />

              {/* Girdle */}
              <line x1="22" y1="118" x2="198" y2="118" stroke="#6868a0" strokeWidth="1.5" />

              {/* Pavilion — 5 main facets (each spectrum colour) */}
              <polygon className={s.fP1} points="22,118 66,118 110,262"   stroke="#8888b2" strokeWidth="1.0" />
              <polygon className={s.fP2} points="66,118 110,118 110,262"  stroke="#8888b2" strokeWidth="1.0" />
              <polygon className={s.fP3} points="110,118 154,118 110,262" stroke="#8888b2" strokeWidth="1.0" />
              <polygon className={s.fP4} points="154,118 198,118 110,262" stroke="#8888b2" strokeWidth="1.0" />
              {/* Half-facets for detail */}
              <polygon className={s.fP5} points="22,118 44,118 110,262"   stroke="#9898c0" strokeWidth="0.8" />
              <polygon className={s.fP1} points="176,118 198,118 110,262" stroke="#9898c0" strokeWidth="0.8" />
              {/* Pavilion structure lines */}
              <line x1="66"  y1="118" x2="110" y2="262" stroke="#9090ba" strokeWidth="0.7" />
              <line x1="110" y1="118" x2="110" y2="262" stroke="#9090ba" strokeWidth="0.7" />
              <line x1="154" y1="118" x2="110" y2="262" stroke="#9090ba" strokeWidth="0.7" />

              {/* Outer outline */}
              <polygon points="78,42 142,42 198,118 110,262 22,118" fill="none" stroke="#4c4c88" strokeWidth="2.2" strokeLinejoin="round" />
              <polygon points="78,42 142,42 164,80 56,80"           fill="none" stroke="#5a5a94" strokeWidth="1.4" />

              {/* Internal laser dispersion rays */}
              <line className={`${s.intRay} ${s.ir1}`} x1="110" y1="42" x2="22"  y2="118" strokeWidth="0.9" strokeDasharray="100" />
              <line className={`${s.intRay} ${s.ir2}`} x1="110" y1="42" x2="66"  y2="118" strokeWidth="0.9" strokeDasharray="100" />
              <line className={`${s.intRay} ${s.ir3}`} x1="110" y1="42" x2="110" y2="118" strokeWidth="0.9" strokeDasharray="100" />
              <line className={`${s.intRay} ${s.ir4}`} x1="110" y1="42" x2="154" y2="118" strokeWidth="0.9" strokeDasharray="100" />
              <line className={`${s.intRay} ${s.ir5}`} x1="110" y1="42" x2="198" y2="118" strokeWidth="0.9" strokeDasharray="100" />

              {/* Culet + crown sparkle */}
              <circle cx="110" cy="262" r="4"   fill="white" opacity="0.9" />
              <circle cx="110" cy="262" r="2"   fill="white" />
              <circle cx="110" cy="62"  r="3.5" fill="white" opacity="0.85" />
              <circle cx="110" cy="62"  r="1.5" fill="white" />
            </g>
          </svg>

          {/* Exit beams anchored at culet (110, 262) */}
          <div className={s.beamsWrap} style={{ top: 262, left: 110 }}>
            <div className={`${s.exitGlow} ${s.eg1}`} />
            <div className={`${s.exitGlow} ${s.eg2}`} />
            <div className={`${s.exitGlow} ${s.eg3}`} />
            <div className={`${s.exitGlow} ${s.eg4}`} />
            <div className={`${s.exitGlow} ${s.eg5}`} />
            <div className={`${s.exitBeam} ${s.eb1}`} />
            <div className={`${s.exitBeam} ${s.eb2}`} />
            <div className={`${s.exitBeam} ${s.eb3}`} />
            <div className={`${s.exitBeam} ${s.eb4}`} />
            <div className={`${s.exitBeam} ${s.eb5}`} />
          </div>
        </div>

        {/* Text */}
        <div className={s.textBlock}>
          <div className={s.prismaName}>PRISMA</div>
          <div className={s.spectrumLine} />
          <div className={s.taglineWrap}>
            <div className={s.taglineMain}>See through every company.</div>
            <div className={s.dimRow}>
              <span className={`${s.dimTag} ${s.dt1}`}>Quality</span>
              <div className={s.dimDivider} />
              <span className={`${s.dimTag} ${s.dt2}`}>Trend</span>
              <div className={s.dimDivider} />
              <span className={`${s.dimTag} ${s.dt3}`}>Value</span>
              <div className={s.dimDivider} />
              <span className={`${s.dimTag} ${s.dt4}`}>Risk</span>
              <div className={s.dimDivider} />
              <span className={`${s.dimTag} ${s.dt5}`}>Diversification</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
