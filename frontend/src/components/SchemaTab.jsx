import React, { useMemo } from 'react';
import {
  Accordion,
  AccordionButton,
  AccordionIcon,
  AccordionItem,
  AccordionPanel,
  Badge,
  Box,
  Code,
  HStack,
  Table,
  Tbody,
  Td,
  Th,
  Thead,
  Tr,
  Text,
} from '@chakra-ui/react';

export default function SchemaTab({ schema }) {
  const relations = useMemo(() => schema?.relations || [], [schema]);

  return (
    <Box>
      <Text color="gray.700" mb={4}>
        This is a snapshot of the tables/views in your database and their columns.
      </Text>

      <Accordion allowMultiple>
        {relations.map((rel) => {
          const title = `${rel.schema}.${rel.name}`;
          return (
            <AccordionItem key={title} borderRadius="md">
              <h2>
                <AccordionButton>
                  <Box flex="1" textAlign="left">
                    <HStack gap={3}>
                      <Code>{title}</Code>
                      <Badge colorScheme={rel.type === 'table' ? 'blue' : 'teal'}>
                        {rel.type}
                      </Badge>
                      {typeof rel.row_estimate === 'number' ? (
                        <Badge variant="subtle">~{rel.row_estimate} rows</Badge>
                      ) : null}
                    </HStack>
                  </Box>
                  <AccordionIcon />
                </AccordionButton>
              </h2>
              <AccordionPanel>
                <Box overflowX="auto" borderWidth="1px" borderRadius="md">
                  <Table size="sm">
                    <Thead>
                      <Tr>
                        <Th>Column</Th>
                        <Th>Type</Th>
                        <Th>Not null</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {(rel.columns || []).map((c) => (
                        <Tr key={`${title}.${c.name}`}>
                          <Td>
                            <Code>{c.name}</Code>
                          </Td>
                          <Td>{c.type}</Td>
                          <Td>{c.not_null ? 'yes' : 'no'}</Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </Box>

                {rel.definition ? (
                  <Box mt={4}>
                    <Text fontWeight="semibold" mb={2}>
                      View definition
                    </Text>
                    <Box borderWidth="1px" borderRadius="md" p={3} overflowX="auto">
                      <Code whiteSpace="pre">{rel.definition}</Code>
                    </Box>
                  </Box>
                ) : null}
              </AccordionPanel>
            </AccordionItem>
          );
        })}
      </Accordion>
    </Box>
  );
}
