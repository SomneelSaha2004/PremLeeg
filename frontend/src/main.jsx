import React from 'react';
import ReactDOM from 'react-dom/client';
import { ChakraProvider, Container } from '@chakra-ui/react';
import App from './App.jsx';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ChakraProvider>
      <Container maxW="7xl" py={6}>
        <App />
      </Container>
    </ChakraProvider>
  </React.StrictMode>
);
