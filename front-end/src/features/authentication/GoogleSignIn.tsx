import { useEffect, useRef } from 'react';



/**
 * The "continue with Google" button, rendered by Google's own library.
 *
 * **Their button and not ours**, because their terms require their branding, and because the
 * thing it produces - a signed ID token - is only obtainable through their library anyway.
 * What arrives here is that token; the server checks its signature against Google's published
 * keys before it means anything at all.
 *
 * It renders nothing when `VITE_GOOGLE_CLIENT_ID` is empty, exactly like the mail server and
 * the error monitor: wired, inert, and waiting for one value.
 */

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

const SCRIPT = 'https://accounts.google.com/gsi/client';

/**
 * Whether this build has a client id at all.
 *
 * Exported because **the divider above the button has to disappear with it.** A rule reading
 * "or" with nothing underneath is worse than no rule: it reads as a button that failed to
 * load rather than as a feature that is not configured.
 */
export const GOOGLE_ENABLED = Boolean(CLIENT_ID);


// Loaded once for the whole app, however many buttons ask for it. Two screens can hold a
// button at the same time, and a second <script> tag would re-initialise the library under
// the first one's feet.
let loading: Promise<void> | null = null;

function library(): Promise<void> {
  if (loading) return loading;

  loading = new Promise<void>((resolve, reject) => {
    if ((window as any).google?.accounts?.id) return resolve();

    const tag = document.createElement('script');
    tag.src = SCRIPT;
    tag.async = true;
    tag.defer = true;
    tag.onload = () => resolve();
    tag.onerror = () => reject(new Error('Google sign-in library did not load.'));

    document.head.appendChild(tag);
  });

  return loading;
}


type Props = {
  onCredential: (credential: string) => void;

  /**
   * Whether to show Google's own prompt over the page as well as the button.
   *
   * **It is a prompt and never a silent sign-in.** `auto_select` would put somebody back into
   * the account the moment they land on the page, and on a product holding a trading record a
   * session that begins without a deliberate act is the wrong default - most of all for the
   * person who just pressed "log out" and got a shared machine back. One tap is one tap; it
   * costs a click and keeps the act.
   */
  oneTap?: boolean;

  text?: 'signin_with' | 'signup_with' | 'continue_with';
};


const GoogleSignIn = ({ onCredential, oneTap = false, text = 'continue_with' }: Props) => {
  const slot = useRef<HTMLDivElement>(null);

  // The callback is read through a ref rather than closed over, so that Google's library is
  // initialised once and still calls the current handler.
  const handler = useRef(onCredential);
  handler.current = onCredential;

  useEffect(() => {
    if (!CLIENT_ID || !slot.current) return;

    let cancelled = false;

    library()
      .then(() => {
        if (cancelled || !slot.current) return;

        const google = (window as any).google;

        google.accounts.id.initialize({
          client_id: CLIENT_ID,
          callback: (response: { credential?: string }) => {
            if (response?.credential) handler.current(response.credential);
          },
          auto_select: false,
          cancel_on_tap_outside: true,
          itp_support: true,
        });

        google.accounts.id.renderButton(slot.current, {
          type: 'standard',
          // **`outline` and not one of the filled themes, and that is the whole fix for how it
          // looked.** On `filled_black` Google seats the logo in a white chip that runs the
          // full height of the button and pushes past its rounded end - which reads as an icon
          // with no margin, cut off at the edge. None of that is reachable from here: the
          // button is Google's own markup, and on some loads an iframe on their origin, so no
          // stylesheet of ours can touch it. Choosing the variant is the only control there is,
          // and this is the one whose logo has room around it.
          theme: 'outline',
          size: 'large',
          shape: 'pill',
          text,
          locale: 'he',
          // **`left` and not `center`, and the difference is the gap.** With `center` Google
          // centres the logo and the label together as one block, so the mark ends up pressed
          // against the first letter with nothing between them. With `left` the mark sits at
          // the button's starting edge and the label is centred in what is left, which is the
          // spacing their own buttons have everywhere else. In a right-to-left page `left`
          // means the starting edge, so the mark lands on the right - which is where it
          // belongs here.
          logo_alignment: 'left',
          // **Twenty less than the space there is, because Google renders the button into a
          // frame 20px wider than the width asked for** and bleeds it outwards with negative
          // margins. Asking for the full width made that frame overflow the slot, and the
          // global `max-width: 100%` then squeezed it back - which is what cut the logo off.
          // Their own limits are 200 to 400; measured now rather than at mount, when the form
          // may not have been laid out yet.
          width: Math.min(400, Math.max(200, Math.round(slot.current.getBoundingClientRect().width) - 20 || 320)),
        });

        if (oneTap) google.accounts.id.prompt();
      })
      .catch(() => {
        // A blocked or unreachable library is not an error worth a message: the password form
        // beside it is a complete way in, and a red toast about a third party nobody asked
        // for reads as the product being broken.
      });

    return () => { cancelled = true; };
  }, [oneTap, text]);

  if (!CLIENT_ID) return null;

  return (
    <div className="google-signin">
      <div className="google-signin-slot" ref={slot} />
    </div>
  );
};


/**
 * Told to Google when the trader signs out here.
 *
 * Without it, their library keeps treating the account as the chosen one, and One Tap starts
 * offering to put him straight back into the session he just left.
 */
export function forgetGoogleSession() {
  try {
    (window as any).google?.accounts?.id?.disableAutoSelect();
  } catch { /* the library was never loaded, which is the same outcome */ }
}


export default GoogleSignIn;
