import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Container,
  Flex,
  Heading,
  HStack,
  Icon,
  Link,
  Spinner,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Text,
  Badge,
  VStack,
} from '@chakra-ui/react';

import { fetchGoldenPrompts, fetchSchema } from './api.js';
import SchemaTab from './components/SchemaTab.jsx';
import ChatTab from './components/ChatTab.jsx';
import GuidelinesTab from './components/GuidelinesTab.jsx';
import ArchitectureTab from './components/ArchitectureTab.jsx';

// Simple icon components
const DatabaseIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M12 3C7.58 3 4 4.79 4 7v10c0 2.21 3.58 4 8 4s8-1.79 8-4V7c0-2.21-3.58-4-8-4zm0 2c3.87 0 6 1.5 6 2s-2.13 2-6 2-6-1.5-6-2 2.13-2 6-2zm6 12c0 .5-2.13 2-6 2s-6-1.5-6-2v-2.23c1.61.78 3.72 1.23 6 1.23s4.39-.45 6-1.23V17zm0-5c0 .5-2.13 2-6 2s-6-1.5-6-2V9.77c1.61.78 3.72 1.23 6 1.23s4.39-.45 6-1.23V12z"/>
  </Icon>
);

const ChatIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/>
  </Icon>
);

const BookIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M18 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 4h5v8l-2.5-1.5L6 12V4z"/>
  </Icon>
);

const ArchitectureIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M22 9V7h-2V5c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-2h2v-2h-2v-2h2v-2h-2V9h2zm-4 10H4V5h14v14zM6 13h5v4H6zm6-6h4v3h-4zM6 7h5v5H6zm6 4h4v6h-4z"/>
  </Icon>
);

const GithubIcon = (props) => (
  <Icon viewBox="0 0 24 24" {...props}>
    <path fill="currentColor" d="M12 2A10 10 0 0 0 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.92 0-1.11.38-2 1.03-2.71-.1-.25-.45-1.29.1-2.64 0 0 .84-.27 2.75 1.02.79-.22 1.65-.33 2.5-.33.85 0 1.71.11 2.5.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.35.2 2.39.1 2.64.65.71 1.03 1.6 1.03 2.71 0 3.82-2.34 4.66-4.57 4.91.36.31.69.92.69 1.85V21c0 .27.16.59.67.5C19.14 20.16 22 16.42 22 12A10 10 0 0 0 12 2z"/>
  </Icon>
);

export default function App() {
  const [schema, setSchema] = useState(null);
  const [golden, setGolden] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setLoadError(null);
      try {
        const [schemaData, goldenData] = await Promise.all([
          fetchSchema(),
          fetchGoldenPrompts(5),
        ]);
        if (cancelled) return;
        setSchema(schemaData);
        setGolden(goldenData);
      } catch (e) {
        if (cancelled) return;
        setLoadError(e?.message || 'Failed to load initial data');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const relationCount = useMemo(() => schema?.relations?.length || 0, [schema]);
  const tableCount = useMemo(() => schema?.relations?.filter(r => r.type === 'table').length || 0, [schema]);
  const viewCount = useMemo(() => schema?.relations?.filter(r => r.type === 'view').length || 0, [schema]);

  return (
    <Box minH="100vh" display="flex" flexDirection="column">
      {/* Hero Header */}
      <Box
        bgGradient="linear(to-r, brand.600, accent.500)"
        color="white"
        py={8}
        px={4}
        position="relative"
        overflow="hidden"
      >
        <Box
          position="absolute"
          top={0}
          left={0}
          right={0}
          bottom={0}
          opacity={0.15}
          bgSize="30px 30px"
          bgImage="radial-gradient(circle, rgba(255,255,255,0.3) 1px, transparent 1px)"
        />
        <Container maxW="7xl" position="relative">
          <VStack spacing={3} align="start">
            <HStack spacing={3}>
              <Heading size="xl" fontWeight="bold">
                ⚽ PLQuery
              </Heading>
              <Badge
                bg="whiteAlpha.200"
                color="white"
                fontSize="xs"
                px={2}
                py={1}
                borderRadius="full"
              >
                v1.0 MVP
              </Badge>
            </HStack>
            <Text fontSize="lg" opacity={0.9} maxW="2xl">
              Ask questions about Premier League data in plain English. 
              Powered by an AI SQL agent that generates, validates, and executes queries automatically.
            </Text>
            <HStack spacing={4} pt={2} wrap="wrap">
              <Badge bg="whiteAlpha.200" color="white" px={3} py={1} borderRadius="full">
                <HStack spacing={1}>
                  <DatabaseIcon boxSize={4} />
                  <Text>{tableCount} tables, {viewCount} views</Text>
                </HStack>
              </Badge>
              <Badge bg="whiteAlpha.200" color="white" px={3} py={1} borderRadius="full">
                25 seasons of data
              </Badge>
              <Badge bg="whiteAlpha.200" color="white" px={3} py={1} borderRadius="full">
                Multi-query mode
              </Badge>
            </HStack>
          </VStack>
        </Container>
      </Box>

      {/* Main Content */}
      <Container maxW="7xl" py={8} flex="1">
        {loading ? (
          <Flex justify="center" align="center" minH="300px">
            <VStack spacing={4}>
              <Spinner size="xl" color="brand.500" thickness="4px" />
              <Text color="gray.600" fontSize="lg">Loading schema & examples…</Text>
            </VStack>
          </Flex>
        ) : loadError ? (
          <Box
            borderWidth="2px"
            borderColor="red.200"
            borderRadius="xl"
            p={8}
            bg="white"
            shadow="sm"
            textAlign="center"
          >
            <Heading size="md" mb={3} color="red.600">
              Could not load demo data
            </Heading>
            <Text color="gray.700" mb={2}>{loadError}</Text>
            <Text color="gray.500">
              Make sure the backend is running on port 8000.
            </Text>
          </Box>
        ) : (
          <Box bg="white" borderRadius="xl" shadow="sm" overflow="hidden">
            <Tabs variant="enclosed" colorScheme="brand" defaultIndex={1}>
              <TabList bg="gray.50" px={4} pt={4}>
                <Tab _selected={{ bg: 'white', borderBottomColor: 'white' }} borderTopRadius="lg">
                  <HStack spacing={2}>
                    <DatabaseIcon boxSize={4} />
                    <Text>Schema</Text>
                  </HStack>
                </Tab>
                <Tab _selected={{ bg: 'white', borderBottomColor: 'white' }} borderTopRadius="lg">
                  <HStack spacing={2}>
                    <ChatIcon boxSize={4} />
                    <Text>Chat</Text>
                  </HStack>
                </Tab>
                <Tab _selected={{ bg: 'white', borderBottomColor: 'white' }} borderTopRadius="lg">
                  <HStack spacing={2}>
                    <BookIcon boxSize={4} />
                    <Text>Guidelines</Text>
                  </HStack>
                </Tab>
                <Tab _selected={{ bg: 'white', borderBottomColor: 'white' }} borderTopRadius="lg">
                  <HStack spacing={2}>
                    <ArchitectureIcon boxSize={4} />
                    <Text>Architecture</Text>
                  </HStack>
                </Tab>
              </TabList>
              <TabPanels>
                <TabPanel p={6}>
                  <SchemaTab schema={schema} />
                </TabPanel>
                <TabPanel p={6}>
                  <ChatTab goldenPrompts={golden} />
                </TabPanel>
                <TabPanel p={6}>
                  <GuidelinesTab goldenPrompts={golden} />
                </TabPanel>
                <TabPanel p={6}>
                  <ArchitectureTab />
                </TabPanel>
              </TabPanels>
            </Tabs>
          </Box>
        )}
      </Container>

      {/* Footer */}
      <Box bg="gray.800" color="gray.300" py={6} mt="auto">
        <Container maxW="7xl">
          <Flex justify="space-between" align="center" wrap="wrap" gap={4}>
            <VStack align="start" spacing={1}>
              <Text fontWeight="semibold" color="white">PLQuery</Text>
              <Text fontSize="sm">
                A natural language SQL agent for Premier League analytics
              </Text>
            </VStack>
            <HStack spacing={6}>
              <VStack align="start" spacing={1}>
                <Text fontSize="xs" textTransform="uppercase" color="gray.500">Tech Stack</Text>
                <Text fontSize="sm">React • FastAPI • PostgreSQL • OpenAI</Text>
              </VStack>
              <Link
                href="https://github.com/SomneelSaha2004/PLQuery"
                isExternal
                _hover={{ color: 'white' }}
              >
                <HStack spacing={2}>
                  <GithubIcon boxSize={5} />
                  <Text fontSize="sm">View on GitHub</Text>
                </HStack>
              </Link>
            </HStack>
          </Flex>
        </Container>
      </Box>
    </Box>
  );
}
