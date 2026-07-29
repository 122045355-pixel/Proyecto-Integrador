import * as DocumentPicker from 'expo-document-picker';


export async function pickSupportedDocument() {
  const result = await DocumentPicker.getDocumentAsync({
    type: [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'image/jpeg',
      'image/png',
    ],
    copyToCacheDirectory: true,
    multiple: false,
  });
  return result.canceled ? null : result.assets[0];
}
