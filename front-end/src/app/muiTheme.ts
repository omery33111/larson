import { createTheme } from '@mui/material/styles';



// ------------------------- MUI THEME -------------------------
//
// MUI is used only for behaviour - popovers, tooltips, gauges - never for layout, so this
// theme is deliberately small. It exists for two reasons:
//
// 1. `direction: rtl`. MUI positions a Popover by measuring against the writing direction.
//    Without being told the document is RTL it anchors menus as if it were LTR, which on a
//    narrow screen pushes the panel clean off the side of the viewport.
// 2. `mode: dark`. Otherwise MUI's own defaults paint light surfaces and near-black text
//    into a dark product.
//
// Colours the components use are still set at the call site, next to the component that
// needs them, so there is one place to look rather than two.

export const muiTheme = createTheme({
  direction: 'rtl',
  palette: {
    mode: 'dark',
    background: {
      paper: '#15181f',
      default: '#0f1115',
    },
    text: {
      primary: '#e8e8e8',
      secondary: '#8b909c',
    },
    primary: {
      main: '#f0b90b',
    },
  },
  typography: {
    fontFamily: "'Rubik', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif",
  },
});
