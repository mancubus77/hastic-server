import * as config from '../config';

import * as nedb from 'nedb';
import * as fs from 'fs';


export enum Collection { ANALYTIC_UNITS, SEGMENTS };


/**
 * Class which helps to make queries to your collection
 *
 * @param { string | object } query: a key as a string or mongodb-style query
 */
export type DBQ = {
  findOne: (query: string | object) => any,
  findMany: (query: string[] | object) => any[],
  insertOne: (document: object) => string,
  insertMany: (documents: object[]) => string[],
  updateOne: (query: string | object, updateQuery: any) => void,
  removeOne: (query: string) => boolean
  removeMany: (query: string[] | object) => number
}

export function makeDBQ(collection: Collection): DBQ {
  return {
    findOne: dbFindOne.bind(null, collection),
    findMany: dbFindMany.bind(null, collection),
    insertOne: dbInsertOne.bind(null, collection),
    insertMany: dbInsertMany.bind(null, collection),
    updateOne: dbUpdateOne.bind(null, collection),
    removeOne: dbRemoveOne.bind(null, collection),
    removeMany: dbRemoveMany.bind(null, collection)
  }
}

function wrapIdToQuery(query: string | object): any {
  if(typeof query === 'string') {
    return { _id: query };
  }
  return query;
}

function wrapIdsToQuery(query: string[] | object): any {
  if(Array.isArray(query)) {
    return { _id: { $in: query } };
  }
  return query;
}

const db = new Map<Collection, nedb>();

let dbInsertOne = (collection: Collection, doc: object) => {
  return new Promise<string>((resolve, reject) => {
    db[collection].insert(doc, (err, newDoc) => {
      if(err) {
        reject(err);
      } else {
        resolve(newDoc._id);
      }
    });
  });
}

let dbInsertMany = (collection: Collection, docs: object[]) => {
  return new Promise<string[]>((resolve, reject) => {
    db[collection].insert(docs, (err, newDocs: any[]) => {
      if(err) {
        reject(err);
      } else {
        resolve(newDocs.map(d => d._id));
      }
    });
  });
}

let dbUpdateOne = (collection: Collection, query: string | object, updateQuery: object) => {
  query = wrapIdToQuery(query);
  return new Promise<void>((resolve, reject) => {
    db[collection].update(query, updateQuery, { /* options */ }, (err: Error) => {
      if(err) {
        reject(err);
      } else {
        resolve();
      }
    });
  });
}

let dbFindOne = (collection: Collection, query: string | object) => {
  query = wrapIdToQuery(query);
  return new Promise<any>((resolve, reject) => {
    db[collection].findOne(query, (err, doc) => {
      if(err) {
        reject(err);
      } else {
        resolve(doc);
      }
    });
  });
}

let dbFindMany = (collection: Collection, query: string[] | object) => {
  query = wrapIdsToQuery(query);
  return new Promise<any[]>((resolve, reject) => {
    db[collection].findOne(query, (err, docs) => {
      if(err) {
        reject(err);
      } else {
        resolve(docs);
      }
    });
  });
}

let dbRemoveOne = (collection: Collection, id: string) => {
  let query = { _id: id };
  return new Promise<boolean>((resolve, reject) => {
    db[collection].remove(query, (err, numRemoved) => {
      if(err) {
        reject(err);
      } else {
        if(numRemoved > 1) {
          throw new Error(`Removed ${numRemoved} elements with id: ${id}. Only one is Ok.`);
        } else {
          resolve(numRemoved == 1);
        }
      }
    });
  });
}

let dbRemoveMany = (collection: Collection, query: string[] | object) => {
  query = wrapIdsToQuery(query);
  return new Promise<number>((resolve, reject) => {
    db[collection].remove(query, (err, numRemoved) => {
      if(err) {
        reject(err);
      } else {
        resolve(numRemoved);
      }
    });
  });
}


function maybeCreateDir(path: string): void {
  if(fs.existsSync(path)) {
    return;
  }
  console.log('mkdir: ' + path);
  fs.mkdirSync(path);
}

function checkDataFolders(): void {
  [
    config.DATA_PATH,
    config.ZMQ_IPC_PATH
  ].forEach(maybeCreateDir);
}
checkDataFolders();

// TODO: it's better if models request db which we create if it`s needed
db[Collection.ANALYTIC_UNITS] = new nedb({ filename: config.ANALYTIC_UNITS_DATABASE_PATH, autoload: true });
db[Collection.SEGMENTS] = new nedb({ filename: config.SEGMENTS_DATABASE_PATH, autoload: true });
