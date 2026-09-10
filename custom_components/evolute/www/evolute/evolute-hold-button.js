/*
 * evolute-hold-button
 *
 * A command button for the Evolute integration that has to be held rather than
 * tapped, because every command it can send (unlocking the car, opening the trunk)
 * is something an accidental touch must not trigger.
 *
 * It also renders the two things a plain `type: button` card cannot show:
 *   - whether the vehicle currently accepts the command  (attribute `blocked`)
 *   - that a sent command has not been confirmed by the car yet (attribute `pending`)
 *
 * Config:
 *   type: custom:evolute-hold-button
 *   entity: button.evolute_<car_id>_central_lock_toggle
 *   name: Замок                     # optional, defaults to the entity name
 *   icon: mdi:lock-outline          # optional, defaults to the entity icon
 *   state_entity: binary_sensor.evolute_<car_id>_central_lock   # optional
 *   state_labels: { on: Открыт, off: Закрыт }                   # optional
 *   hold_time: 700                  # ms to hold, default 700
 *   require_hold: true              # set false for a plain tap
 */

const HOLD_TIME_DEFAULT = 700;
const LOCAL_PENDING_MS = 8000;
const RING_RADIUS = 22;
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;

class EvoluteHoldButton extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._holdTimer = null;
    this._pendingTimer = null;
    this._localPendingUntil = 0;
    this._holding = false;
    this._rendered = false;
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("evolute-hold-button: 'entity' is required");
    }
    if (!config.entity.startsWith("button.")) {
      throw new Error("evolute-hold-button: 'entity' must be a button entity");
    }
    this._config = {
      hold_time: HOLD_TIME_DEFAULT,
      require_hold: true,
      ...config,
    };
    this._rendered = false;
    if (this.shadowRoot.childElementCount) {
      this._build();
      this._update();
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._rendered) {
      this._build();
    }
    this._update();
  }

  getCardSize() {
    return 1;
  }

  static getStubConfig() {
    return { entity: "", name: "Команда", require_hold: true };
  }

  // --- rendering --------------------------------------------------------

  _build() {
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .card {
          position: relative;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 6px;
          box-sizing: border-box;
          padding: 14px 8px 12px;
          min-height: 108px;
          border-radius: var(--ha-card-border-radius, 12px);
          border: var(--ha-card-border-width, 1px) solid
                  var(--ha-card-border-color, var(--divider-color, #e0e0e0));
          background: var(--ha-card-background, var(--card-background-color, #fff));
          box-shadow: var(--ha-card-box-shadow, none);
          color: var(--primary-text-color);
          cursor: pointer;
          user-select: none;
          -webkit-user-select: none;
          -webkit-tap-highlight-color: transparent;
          touch-action: manipulation;
          transition: transform 120ms ease, opacity 120ms ease;
        }
        .card:focus-visible {
          outline: 2px solid var(--primary-color);
          outline-offset: 2px;
        }
        .card.holding { transform: scale(0.96); }
        .card.disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .card.nudge { animation: nudge 320ms ease; }
        @keyframes nudge {
          0%, 100% { transform: translateX(0); }
          20% { transform: translateX(-5px); }
          40% { transform: translateX(5px); }
          60% { transform: translateX(-3px); }
          80% { transform: translateX(3px); }
        }

        .dial { position: relative; width: 52px; height: 52px; }
        .dial svg {
          position: absolute;
          inset: 0;
          transform: rotate(-90deg);
          overflow: visible;
        }
        .track {
          fill: none;
          stroke: var(--divider-color, #e0e0e0);
          stroke-width: 3;
        }
        .progress {
          fill: none;
          stroke: var(--primary-color, #03a9f4);
          stroke-width: 3;
          stroke-linecap: round;
          stroke-dasharray: ${RING_CIRCUMFERENCE};
          stroke-dashoffset: ${RING_CIRCUMFERENCE};
          transition: stroke-dashoffset 150ms linear;
        }
        .card.pending .progress {
          stroke-dasharray: ${RING_CIRCUMFERENCE * 0.25} ${RING_CIRCUMFERENCE};
          stroke-dashoffset: 0;
          transform-origin: 50% 50%;
          animation: spin 1s linear infinite;
          transition: none;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        ha-icon {
          position: absolute;
          inset: 0;
          margin: auto;
          width: 26px;
          height: 26px;
          --mdc-icon-size: 26px;
          color: var(--state-icon-color, var(--paper-item-icon-color, #44739e));
        }
        .card.active ha-icon { color: var(--state-active-color, var(--primary-color)); }
        .card.pending ha-icon { color: var(--primary-color); }
        .card.disabled ha-icon { color: var(--disabled-text-color, #bdbdbd); }

        .name {
          font-size: 14px;
          font-weight: 500;
          text-align: center;
          line-height: 1.2;
        }
        .state {
          font-size: 12px;
          color: var(--secondary-text-color);
          text-align: center;
          line-height: 1.2;
          min-height: 14px;
        }
        .hint {
          position: absolute;
          left: 0;
          right: 0;
          bottom: 4px;
          font-size: 10px;
          text-align: center;
          color: var(--secondary-text-color);
          opacity: 0;
          transition: opacity 150ms ease;
          pointer-events: none;
        }
        .card.hinting .hint { opacity: 1; }
      </style>
      <div class="card" tabindex="0" role="button">
        <div class="dial">
          <svg viewBox="0 0 52 52">
            <circle class="track" cx="26" cy="26" r="${RING_RADIUS}"></circle>
            <circle class="progress" cx="26" cy="26" r="${RING_RADIUS}"></circle>
          </svg>
          <ha-icon></ha-icon>
        </div>
        <div class="name"></div>
        <div class="state"></div>
        <div class="hint">удерживайте</div>
      </div>
    `;

    this._card = this.shadowRoot.querySelector(".card");
    this._progress = this.shadowRoot.querySelector(".progress");
    this._iconEl = this.shadowRoot.querySelector("ha-icon");
    this._nameEl = this.shadowRoot.querySelector(".name");
    this._stateEl = this.shadowRoot.querySelector(".state");

    this._card.addEventListener("pointerdown", (ev) => this._onPointerDown(ev));
    this._card.addEventListener("pointerup", (ev) => this._onPointerUp(ev));
    this._card.addEventListener("pointercancel", () => this._cancelHold());
    this._card.addEventListener("pointerleave", () => this._cancelHold());
    this._card.addEventListener("contextmenu", (ev) => ev.preventDefault());
    this._card.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        this._fire();
      }
    });

    this._rendered = true;
  }

  _entityState() {
    if (!this._hass || !this._config) return undefined;
    return this._hass.states[this._config.entity];
  }

  _isPending() {
    const stateObj = this._entityState();
    const remote = Boolean(stateObj && stateObj.attributes.pending);
    return remote || Date.now() < this._localPendingUntil;
  }

  _isBlocked() {
    const stateObj = this._entityState();
    if (!stateObj) return true;
    if (stateObj.state === "unavailable" || stateObj.state === "unknown") return true;
    return Boolean(stateObj.attributes.blocked);
  }

  _stateText() {
    const { state_entity: stateEntity, state_labels: labels } = this._config;
    if (!stateEntity || !this._hass) return "";
    const stateObj = this._hass.states[stateEntity];
    if (!stateObj) return "";
    if (labels && labels[stateObj.state] !== undefined) return labels[stateObj.state];
    return this._hass.formatEntityState
      ? this._hass.formatEntityState(stateObj)
      : stateObj.state;
  }

  _update() {
    if (!this._rendered || !this._hass || !this._config) return;

    const stateObj = this._entityState();
    const pending = this._isPending();
    const blocked = this._isBlocked();

    const name =
      this._config.name ||
      (stateObj && stateObj.attributes.friendly_name) ||
      this._config.entity;
    this._nameEl.textContent = name;
    this._stateEl.textContent = pending ? "отправлено…" : this._stateText();

    let icon = this._config.icon;
    if (pending) {
      icon = "mdi:timer-sand";
    } else if (!icon) {
      icon = (stateObj && stateObj.attributes.icon) || "mdi:gesture-tap-hold";
    }
    this._iconEl.setAttribute("icon", icon);

    this._card.classList.toggle("pending", pending);
    this._card.classList.toggle("disabled", blocked || pending);

    const stateEntityObj =
      this._config.state_entity && this._hass.states[this._config.state_entity];
    this._card.classList.toggle(
      "active",
      !pending && Boolean(stateEntityObj) && stateEntityObj.state === "on"
    );

    this._card.setAttribute(
      "aria-label",
      `${name}${blocked ? " (недоступно)" : ""}${pending ? " (команда отправлена)" : ""}`
    );

    // Re-render once the local pending window lapses, in case the coordinator
    // never reported a pending flag of its own.
    if (Date.now() < this._localPendingUntil) {
      clearTimeout(this._pendingTimer);
      this._pendingTimer = setTimeout(
        () => this._update(),
        this._localPendingUntil - Date.now() + 50
      );
    }
  }

  // --- interaction ------------------------------------------------------

  _onPointerDown(ev) {
    if (ev.button !== undefined && ev.button !== 0) return;
    if (this._isBlocked() || this._isPending()) return;

    if (!this._config.require_hold) return;

    this._holding = true;
    this._card.classList.add("holding", "hinting");
    this._card.setPointerCapture?.(ev.pointerId);

    // Drive the ring from empty to full over exactly the hold duration, so the
    // fill itself is the feedback that tells you how long to keep holding.
    this._progress.style.transition = `stroke-dashoffset ${this._config.hold_time}ms linear`;
    this._progress.style.strokeDashoffset = "0";

    this._holdTimer = setTimeout(() => {
      this._holdTimer = null;
      this._holding = false;
      this._resetRing();
      this._card.classList.remove("holding", "hinting");
      this._fire();
    }, this._config.hold_time);
  }

  _onPointerUp() {
    if (!this._config.require_hold) {
      if (this._isBlocked()) {
        this._reject("Команда сейчас недоступна");
        return;
      }
      if (this._isPending()) return;
      this._fire();
      return;
    }

    if (this._holdTimer) {
      // Released too early: this is the accidental-touch case the card exists for.
      this._cancelHold();
      this._nudge();
      this._haptic("warning");
      this._toast(`${this._config.name || "Кнопка"}: удерживайте ~${Math.round(
        this._config.hold_time / 100
      ) / 10} с для подтверждения`);
      return;
    }

    if (this._isBlocked()) {
      this._reject("Команда сейчас недоступна");
    }
  }

  _cancelHold() {
    if (this._holdTimer) {
      clearTimeout(this._holdTimer);
      this._holdTimer = null;
    }
    if (!this._holding) return;
    this._holding = false;
    this._card.classList.remove("holding", "hinting");
    this._resetRing();
  }

  _resetRing() {
    this._progress.style.transition = "stroke-dashoffset 150ms ease";
    this._progress.style.strokeDashoffset = String(RING_CIRCUMFERENCE);
  }

  _nudge() {
    this._card.classList.remove("nudge");
    // Force a reflow so the animation restarts on every rejected tap.
    void this._card.offsetWidth;
    this._card.classList.add("nudge");
    setTimeout(() => this._card.classList.remove("nudge"), 340);
  }

  _reject(message) {
    this._nudge();
    this._haptic("failure");
    this._toast(message);
  }

  async _fire() {
    if (this._isBlocked()) {
      this._reject("Команда сейчас недоступна");
      return;
    }
    if (this._isPending()) return;

    this._haptic("success");
    this._localPendingUntil = Date.now() + LOCAL_PENDING_MS;
    this._update();

    try {
      await this._hass.callService("button", "press", {
        entity_id: this._config.entity,
      });
    } catch (err) {
      this._localPendingUntil = 0;
      this._update();
      this._reject(`Команда не прошла: ${err.message || err}`);
    }
  }

  _haptic(type) {
    this.dispatchEvent(
      new CustomEvent("haptic", { bubbles: true, composed: true, detail: type })
    );
  }

  _toast(message) {
    this.dispatchEvent(
      new CustomEvent("hass-notification", {
        bubbles: true,
        composed: true,
        detail: { message },
      })
    );
  }
}

customElements.define("evolute-hold-button", EvoluteHoldButton);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "evolute-hold-button",
  name: "Evolute Hold Button",
  description:
    "Кнопка команды Evolute с удержанием, индикацией отправки и блокировкой недоступных команд",
});

console.info("%c EVOLUTE-HOLD-BUTTON %c loaded ", "background:#00c0fc;color:#fff", "");
