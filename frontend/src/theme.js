import { extendTheme } from '@chakra-ui/react';

const theme = extendTheme({
  fonts: {
    heading: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`,
    body: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`,
  },
  colors: {
    brand: {
      50: '#faf5ff',
      100: '#e9d8fd',
      200: '#d6bcfa',
      300: '#b794f4',
      400: '#9f7aea',
      500: '#805ad5',  // Primary purple
      600: '#6b46c1',
      700: '#553c9a',
      800: '#44337a',
      900: '#322659',
    },
    accent: {
      50: '#ffe5f1',
      100: '#ffb8d9',
      200: '#ff8ac0',
      300: '#ff5ca8',
      400: '#ff2e8f',
      500: '#e60073',  // Premier League magenta
      600: '#b4005a',
      700: '#820041',
      800: '#510028',
      900: '#21000f',
    },
  },
  components: {
    Button: {
      defaultProps: {
        colorScheme: 'brand',
      },
    },
    Tabs: {
      variants: {
        enclosed: {
          tab: {
            fontWeight: 'semibold',
            _selected: {
              color: 'brand.600',
              borderColor: 'brand.500',
              borderBottomColor: 'white',
            },
          },
        },
      },
    },
    Badge: {
      defaultProps: {
        colorScheme: 'brand',
      },
    },
    Code: {
      baseStyle: {
        bg: 'gray.100',
        px: 2,
        py: 0.5,
        borderRadius: 'md',
        fontSize: 'sm',
      },
    },
  },
  styles: {
    global: {
      body: {
        bg: 'gray.50',
      },
    },
  },
});

export default theme;
