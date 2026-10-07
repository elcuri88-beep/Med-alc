export interface Source {
  id: string;
  titulo: string;
  tipo: string;
  nota?: string;
}

export interface Claim {
  id: string;
  texto: string;
  fuentes: string[];
  pendienteRevision: boolean;
  notas?: string;
}

export interface Section {
  id: string;
  titulo: string;
  afirmaciones: Claim[];
}

export interface Module {
  id: string;
  orden: number;
  titulo: string;
  resumen: string;
  secciones: Section[];
}

export interface Meta {
  appName: string;
  contentVersion: string;
  lastReview: string | null;
  reviewStatus: string;
  language: string;
  disclaimer: string;
  privacy: string;
  legal: string;
}
